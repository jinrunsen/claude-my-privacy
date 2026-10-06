#!/usr/bin/env python3
"""Check local bilingual Markdown pairs and record reviewed file hashes.

This checker validates the repository's authored Markdown, not translation
meaning. It deliberately does not mutate Git objects, refs, or the index.
"""

import argparse
import hashlib
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_DIRS = {'.git', '.claude', 'node_modules', '__pycache__', '.cache'}
EXCLUDED_TREES = {'.agents', '.agent', '.claude-plugin/types'}
BILINGUAL_TABLE = 'docs/i18n/terminology.md'
INLINE_CODE = re.compile(r'(`+)(.+?)\1')
LINK = re.compile(r'!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)')
REFERENCE_DEFINITION = re.compile(r'^ {0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)(?:\s+"[^"]*")?\s*$')
REFERENCE_LINK = re.compile(r'!?\[([^\]\n]*)\]\[([^\]\n]*)\]')
SHORT_REFERENCE = re.compile(r'!?\[([^\]\n]+)\]')
EXPLICIT_ANCHOR = re.compile(r'<a\s+(?:id|name)=["\x27]([^"\x27]+)["\x27]\s*></a>')


def source_path(path):
    """Map any sibling in a triplet to the English document path."""
    value = str(path)
    if value.endswith('.i18n.yaml'):
        return Path(value[:-10] + '.md')
    if value.endswith('.zh.md'):
        return Path(value[:-6] + '.md')
    return Path(value if value.endswith('.md') else value + '.md')


def siblings(source):
    stem = str(source)[:-3]
    return source, Path(stem + '.zh.md'), Path(stem + '.i18n.yaml')


def is_excluded(relative):
    text = relative.as_posix()
    return text == BILINGUAL_TABLE or any(
        text == prefix or text.startswith(prefix + '/') for prefix in EXCLUDED_TREES
    ) or any(part in EXCLUDED_DIRS for part in relative.parts)


def discover(root):
    """Include remnants of partial deletions and untracked documentation."""
    sources = set()
    for base, dirs, files in os.walk(root, followlinks=False):
        parent = Path(base)
        dirs[:] = [name for name in dirs if not is_excluded((parent / name).relative_to(root))
                   and not (parent / name).is_symlink()]
        for name in files:
            path = parent / name
            if not (name.endswith('.md') or name.endswith('.i18n.yaml')):
                continue
            source = source_path(path)
            if not is_excluded(source.relative_to(root)):
                sources.add(source)
    return sorted(sources)


def blob_hash(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()


def record_text(source):
    en, zh, _ = siblings(source)
    return ''.join(path.name + ': ' + blob_hash(path.read_bytes()) + '\n' for path in (en, zh))


def mask_code(text):
    return INLINE_CODE.sub(lambda match: ' ' * len(match.group()), text)


def slug(text):
    text = LINK.sub(lambda match: match.group().split(']', 1)[0].lstrip('!['), text)
    text = REFERENCE_LINK.sub(lambda match: match[1], text)
    text = re.sub(r'<[^>]+>', '', text).lower()
    return re.sub(r'[^\w\- ]', '', text).replace(' ', '-')


def reference_label(text):
    return ' '.join(text.split()).casefold()


def escaped(text, position):
    backslashes = 0
    while position > 0 and text[position - 1] == '\\':
        backslashes += 1
        position -= 1
    return backslashes % 2 == 1


def parse(text):
    """Extract the structures used by this repository's authored Markdown."""
    signature, inline, links, anchors, prose = [], [], [], set(), []
    problems = []
    fence = None
    body = []
    heading_counts = {}
    switchers = []
    definitions, pending_links = {}, []
    for number, line in enumerate(text.splitlines(), 1):
        if line.rstrip() != line:
            problems.append('trailing whitespace at line ' + str(number))
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})(.*)$', line)
        if fence is not None:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                signature.append(('fence', fence[2], tuple(body), line))
                fence = None
                body = []
            else:
                body.append(line)
            continue
        if marker:
            fence = (marker[1][0], len(marker[1]), line)
            continue
        if re.fullmatch(r'English \| \[中文\]\([^)]+\)|\[English\]\([^)]+\) \| 中文', line):
            switchers.append((number, line))
            continue
        prose.append(line)
        inline.extend(match.group() for match in INLINE_CODE.finditer(line))
        visible = mask_code(line)
        definition = REFERENCE_DEFINITION.fullmatch(visible)
        if definition:
            destination = definition[2].strip('<>')
            label = reference_label(definition[1])
            if label not in definitions:
                definitions[label] = destination
                pending_links.append(('direct', destination))
            continue
        if re.match(r'^ {0,3}\[[^\]]+\]:', visible):
            problems.append('unsupported reference definition at line ' + str(number))
            continue
        matches = []
        for pattern, kind in ((LINK, 'direct'), (REFERENCE_LINK, 'reference'),
                              (SHORT_REFERENCE, 'shortcut')):
            for match in pattern.finditer(visible):
                opening_bracket = match.start() + int(match.group().startswith('!'))
                if escaped(visible, opening_bracket):
                    continue
                if any(match.start() < end and match.end() > start for start, end, _, _ in matches):
                    continue
                if kind == 'direct':
                    value = match[1].strip('<>')
                elif kind == 'reference':
                    value = reference_label(match[2] or match[1])
                else:
                    value = reference_label(match[1])
                matches.append((match.start(), match.end(), kind, value))
        pending_links.extend((kind, value) for _, _, kind, value in sorted(matches))
        anchors.update(EXPLICIT_ANCHOR.findall(visible))
        heading = re.match(r'^(#{1,6})\s+(.+?)\s*#*$', line)
        if heading:
            signature.append(('heading', len(heading[1])))
            anchor = slug(heading[2])
            count = heading_counts.get(anchor, 0)
            heading_counts[anchor] = count + 1
            anchors.add(anchor + ('-' + str(count) if count else ''))
        item = re.match(r'^(\s*)([-+*]|\d+[.)])\s+', line)
        if item:
            kind = 'unordered' if item[2] in '-+*' else item[2]
            signature.append(('list', len(item[1]), kind))
        if visible.strip().startswith('|') and visible.strip().endswith('|'):
            cells = re.split(r'(?<!\\)\|', visible.strip())[1:-1]
            signature.append(('table-row', len(cells)))
    if fence is not None:
        problems.append('unclosed code fence')
    for kind, value in pending_links:
        if kind == 'direct':
            links.append(value)
        elif value in definitions:
            links.append(definitions[value])
        elif kind == 'reference':
            problems.append('undefined reference link: ' + value)
    if not text.endswith('\n') or text.endswith('\n\n'):
        problems.append('expected exactly one final newline')
    if '\r' in text:
        problems.append('use LF line endings')
    return {'signature': signature, 'inline': inline, 'links': links, 'anchors': anchors,
            'prose': prose, 'switchers': switchers, 'lines': len(text.splitlines()),
            'problems': problems}


def read_document(path, cache):
    if path not in cache:
        cache[path] = parse(path.read_bytes().decode('utf-8'))
    return cache[path]


def link_targets(root, path, document, locale, cache):
    targets, errors = [], []
    for destination in document['links']:
        try:
            parts = urlsplit(destination)
        except ValueError:
            errors.append('malformed link: ' + destination)
            continue
        if parts.scheme or destination.startswith('//'):
            targets.append(destination)
            continue
        target = (path.parent / unquote(parts.path)).resolve() if parts.path else path
        try:
            relative = target.relative_to(root)
        except ValueError:
            errors.append('local link escapes the repository: ' + destination)
            continue
        if not target.exists():
            errors.append('broken local link: ' + destination)
        canonical = source_path(target) if target.suffix == '.md' else target
        if parts.path and target.suffix == '.md' and not is_excluded(canonical.relative_to(root)):
            expected = siblings(canonical)[1] if locale == 'zh' else canonical
            if target != expected:
                errors.append('wrong-language document link: ' + destination)
        if parts.fragment and target.is_file() and target.suffix == '.md':
            try:
                if unquote(parts.fragment) not in read_document(target, cache)['anchors']:
                    errors.append('broken local anchor: ' + destination)
            except (OSError, UnicodeError):
                errors.append('cannot inspect linked document as UTF-8: ' + destination)
        normalized = canonical.relative_to(root).as_posix()
        # Do not translate or drop query strings or fragment identifiers.
        suffix = destination[len(parts.path):]
        targets.append(normalized + suffix)
    return targets, errors


def check_pair(root, source, cache=None, require_record=True):
    cache = {} if cache is None else cache
    en, zh, record = siblings(source)
    errors = []
    if record.is_symlink() or (record.exists() and not record.is_file()):
        errors.append('consistency record must be a regular file: ' + record.name)
    if not record.parent.resolve().is_relative_to(root):
        errors.append('consistency record escapes the repository: ' + record.name)
    for path in (en, zh):
        if not path.is_file():
            errors.append('missing ' + path.name)
        elif path.is_symlink():
            errors.append('paired documents must be regular files: ' + path.name)
    if errors:
        return errors
    documents = []
    normalized_links = []
    for path, locale in ((en, 'en'), (zh, 'zh')):
        try:
            document = read_document(path, cache)
        except (OSError, UnicodeError):
            errors.append(path.name + ': cannot read document as UTF-8')
            continue
        documents.append(document)
        errors.extend(path.name + ': ' + problem for problem in document['problems'])
        expected = 'English | [中文](' + zh.name + ')' if locale == 'en' else '[English](' + en.name + ') | 中文'
        if (document['switchers'] != [(3, expected)] or not document['prose']
                or not document['prose'][0].startswith('# ')):
            errors.append(path.name + ': expected one language switcher after H1 on line 3')
        targets, problems = link_targets(root, path, document, locale, cache)
        normalized_links.append(targets)
        errors.extend(path.name + ': ' + problem for problem in problems)
    if len(documents) == 2:
        for field, description in [('signature', 'Markdown structure or fenced code'),
                                   ('inline', 'inline code'), ('lines', 'physical line count')]:
            if documents[0][field] != documents[1][field]:
                errors.append(description + ' differs between languages')
        if normalized_links[0] != normalized_links[1]:
            errors.append('semantic link targets or link order differ between languages')
    if require_record:
        if not record.is_file():
            errors.append('missing ' + record.name)
        else:
            try:
                if record.read_text(encoding='utf-8') != record_text(source):
                    errors.append('stale or malformed consistency record: ' + record.name)
            except (OSError, UnicodeError):
                errors.append('cannot read consistency record as UTF-8: ' + record.name)
    return errors


def main(argv=None, root=None):
    root = (ROOT if root is None else Path(root)).resolve()
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--write', action='store_true', help='record explicitly reviewed pairs')
    mode.add_argument('--list', action='store_true', help='list pair states without writing')
    parser.add_argument('--all', action='store_true', help='explicitly select all pairs for --write')
    parser.add_argument('pairs', nargs='*', help='English, Chinese, record path, or bare stem')
    args = parser.parse_args(argv)
    if args.write and not args.pairs and not args.all:
        parser.error('--write requires pair paths or --all')
    if args.all and (not args.write or args.pairs):
        parser.error('--all is only valid with --write and no pair paths')
    if args.pairs:
        sources = []
        for value in args.pairs:
            source = source_path(root / value).resolve()
            if not source.is_relative_to(root) or is_excluded(source.relative_to(root)):
                parser.error('pair is outside the active corpus: ' + value)
            sources.append(source)
        sources = sorted(set(sources))
    else:
        sources = discover(root)
    if not sources:
        print('No document pairs found.', file=sys.stderr)
        return 1
    cache = {}
    results = [(source, check_pair(root, source, cache, not args.write)) for source in sources]
    # Check all selected pairs before writing any confirmation.
    failed = False
    for source, errors in results:
        relative = source.relative_to(root).as_posix()
        if args.list:
            state = 'missing' if any(error.startswith('missing ') for error in errors) else 'out-of-sync' if errors else 'ok'
            print(state + ' ' + relative)
        elif errors:
            failed = True
            for error in errors:
                print(relative + ': ' + error, file=sys.stderr)
    if args.list:
        return 0
    if failed:
        return 1
    if args.write:
        staged = []
        try:
            for source in sources:
                record = siblings(source)[2]
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                                 dir=record.parent, delete=False) as handle:
                    temporary = Path(handle.name)
                    staged.append((temporary, record))
                    handle.write(record_text(source))
                temporary.chmod(0o644)
            for temporary, record in staged:
                os.replace(temporary, record)
        except (OSError, UnicodeError) as error:
            print('Could not write consistency records: ' + str(error), file=sys.stderr)
            return 1
        finally:
            for temporary, _ in staged:
                temporary.unlink(missing_ok=True)
        print('Recorded ' + str(len(sources)) + ' reviewed pair(s).')
    else:
        print('Checked ' + str(len(sources)) + ' bilingual pair(s): all passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

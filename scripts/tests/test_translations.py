"""Exercise the documentation gate with valid and deliberately broken pairs."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location('translations', Path(__file__).resolve().parents[1] / 'check-translations.py')
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class TranslationChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.pair('README')

    def pair(self, name, en_tail='', zh_tail=''):
        en = '# Guide\n\nEnglish | [中文](' + Path(name).name + '.zh.md)\n\nRead `example`.\n' + en_tail
        zh = '# 指南\n\n[English](' + Path(name).name + '.md) | 中文\n\n阅读 `example`。\n' + zh_tail
        for suffix, content in (('.md', en), ('.zh.md', zh)):
            path = self.root / (name + suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    def run_gate(self, *args):
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            return GATE.main(list(args), self.root)

    def edit(self, name, before, after):
        path = self.root / name
        path.write_text(path.read_text().replace(before, after))

    def test_record_and_check_without_git_or_dependencies(self):
        self.assertEqual(self.run_gate('--write', 'README.md'), 0)
        self.assertEqual(self.run_gate(), 0)
        self.assertFalse((self.root / '.git').exists())

    def test_blob_hash_matches_git_object_format(self):
        self.assertEqual(GATE.blob_hash(b''), 'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391')

    def test_missing_counterpart_cannot_be_recorded(self):
        (self.root / 'README.zh.md').unlink()
        self.assertEqual(self.run_gate('--write', '--all'), 1)
        self.assertFalse((self.root / 'README.i18n.yaml').exists())

    def test_missing_record_and_stale_content_fail(self):
        self.assertEqual(self.run_gate(), 1)
        self.assertEqual(self.run_gate('--write', 'README'), 0)
        self.edit('README.md', 'Read', 'Inspect')
        self.assertEqual(self.run_gate(), 1)

    def test_changed_code_block_cannot_be_confirmed(self):
        self.pair('README', '\n```sh\necho example\n```\n', '\n```sh\necho changed\n```\n')
        self.assertEqual(self.run_gate('--write', 'README'), 1)

    def test_changed_inline_code_fails(self):
        self.edit('README.zh.md', '`example`', '`different`')
        self.assertEqual(self.run_gate('--write', 'README'), 1)

    def test_code_delimiters_are_preserved_verbatim(self):
        self.pair('README', '\n```sh\necho example\n```\n', '\n~~~sh\necho example\n~~~\n')
        self.assertEqual(self.run_gate('--write', 'README'), 1)
        self.pair('README')
        self.edit('README.zh.md', '`example`', '``example``')
        self.assertEqual(self.run_gate('--write', 'README'), 1)

    def test_same_language_links_pass_but_cross_language_link_fails(self):
        self.pair('other')
        self.pair('README', '\n[Other](other.md)\n', '\n[其他](other.zh.md)\n')
        self.assertEqual(self.run_gate('--write', '--all'), 0)
        self.edit('README.zh.md', 'other.zh.md', 'other.md')
        self.assertEqual(self.run_gate('--write', 'README'), 1)

    def test_shared_anchor_and_exact_fragment(self):
        self.pair('README', '\n[Use](#use)\n\n<a id="use"></a>\n\n## Use\n',
                  '\n[用法](#use)\n\n<a id="use"></a>\n\n## 用法\n')
        self.assertEqual(self.run_gate('--write', 'README'), 0)
        self.edit('README.zh.md', '(#use)', '(#missing)')
        self.assertEqual(self.run_gate('--write', 'README'), 1)

    def test_list_and_table_structure_must_match(self):
        self.pair('README', '\n- One\n', '\n1. 一\n')
        self.assertEqual(self.run_gate('--write', 'README'), 1)
        self.pair('README', '\n| One | Two |\n', '\n| 一 |\n')
        self.assertEqual(self.run_gate('--write', 'README'), 1)

    def test_line_count_must_match(self):
        self.edit('README.zh.md', '阅读', '\n阅读')
        self.assertEqual(self.run_gate('--write', 'README'), 1)

    def test_partial_deletion_is_discovered_from_record(self):
        self.assertEqual(self.run_gate('--write', 'README'), 0)
        (self.root / 'README.md').unlink()
        (self.root / 'README.zh.md').unlink()
        self.assertEqual(self.run_gate(), 1)

    def test_literal_links_in_code_are_not_followed(self):
        tail = '\n`[example](missing.md)`\n\n```md\n[example](absent.md)\n```\n'
        self.pair('README', tail, tail)
        self.assertEqual(self.run_gate('--write', 'README'), 0)

    def test_anchor_inside_inline_code_does_not_exist(self):
        tail = '\n[Jump](#use)\n\n`<a id="use"></a>`\n'
        self.pair('README', tail, tail)
        self.assertEqual(self.run_gate('--write', 'README'), 1)

    def test_linked_heading_uses_visible_label_for_anchor(self):
        tail = '\n[Jump](#usage)\n\n## [Usage](https://example.com)\n'
        self.pair('README', tail, tail)
        self.assertEqual(self.run_gate('--write', 'README'), 0)

    def test_reference_links_validate_destinations_and_locales(self):
        self.pair('other')
        self.pair('README', '\n[Other][ref]\n\n[ref]: other.md\n',
                  '\n[其他][参考]\n\n[参考]: other.zh.md\n')
        self.assertEqual(self.run_gate('--write', '--all'), 0)
        self.edit('README.zh.md', 'other.zh.md', 'other.md')
        self.assertEqual(self.run_gate('--write', 'README'), 1)
        tail = '\n[Missing][ref]\n\n[ref]: absent.md\n'
        self.pair('README', tail, tail)
        self.assertEqual(self.run_gate('--write', 'README'), 1)

    def test_collapsed_and_shortcut_references_are_resolved(self):
        tail = '\n[Ref][] and [Ref].\n\n[ref]: https://example.com\n'
        self.pair('README', tail, tail)
        self.assertEqual(self.run_gate('--write', 'README'), 0)
        tail = '\n[Ref][] and [Ref].\n\n[ref]: absent.md\n'
        self.pair('README', tail, tail)
        self.assertEqual(self.run_gate('--write', 'README'), 1)

    def test_undefined_reference_is_reported(self):
        tail = '\n[Missing][undefined]\n'
        self.pair('README', tail, tail)
        self.assertEqual(self.run_gate('--write', 'README'), 1)

    def test_escaped_opening_brackets_are_not_links(self):
        tail = '\n\\[Ref][] and \\[Missing](absent.md).\n'
        self.pair('README', tail, tail)
        self.assertEqual(self.run_gate('--write', 'README'), 0)

    def test_only_first_reference_definition_is_used(self):
        tail = '\n[Link][ref]\n\n[ref]: https://example.com\n[ref]: absent.md\n'
        self.pair('README', tail, tail)
        self.assertEqual(self.run_gate('--write', 'README'), 0)

    def test_malformed_urls_and_record_encoding_fail_cleanly(self):
        tail = '\n[Bad](http://[)\n'
        self.pair('README', tail, tail)
        self.assertEqual(self.run_gate('--write', 'README'), 1)
        self.pair('README')
        (self.root / 'README.i18n.yaml').write_bytes(b'\xff')
        self.assertEqual(self.run_gate(), 1)

    def test_record_symlink_never_overwrites_external_file(self):
        with tempfile.TemporaryDirectory() as external:
            target = Path(external) / 'keep.txt'
            target.write_text('preserve me')
            (self.root / 'README.i18n.yaml').symlink_to(target)
            self.assertEqual(self.run_gate('--write', 'README'), 1)
            self.assertEqual(target.read_text(), 'preserve me')
            self.assertEqual(self.run_gate(), 1)

    def test_nonregular_record_prevents_all_writes(self):
        self.pair('zzz')
        (self.root / 'zzz.i18n.yaml').mkdir()
        self.assertEqual(self.run_gate('--write', '--all'), 1)
        self.assertFalse((self.root / 'README.i18n.yaml').exists())

    def test_write_requires_explicit_scope_and_does_not_partially_write(self):
        with self.assertRaises(SystemExit), redirect_stderr(StringIO()):
            GATE.main(['--write'], self.root)
        self.pair('broken')
        (self.root / 'broken.zh.md').unlink()
        self.assertEqual(self.run_gate('--write', '--all'), 1)
        self.assertFalse((self.root / 'README.i18n.yaml').exists())

    def test_list_is_read_only_and_local_agent_data_is_excluded(self):
        local_files = [self.root / name for name in (
            '.agents/skills/example/SKILL.md',
            '.agents/UPSTREAM-SKILLS.md',
            '.agents/notes.i18n.yaml',
            '.agent/notes.md',
        )]
        for path in local_files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'\xff Local-only data\n')
        before = {path: path.read_bytes() for path in local_files}
        self.assertEqual(GATE.discover(self.root), [self.root / 'README.md'])
        self.assertEqual(self.run_gate('--list'), 0)
        self.assertFalse((self.root / 'README.i18n.yaml').exists())
        self.assertEqual(self.run_gate('--write', '--all'), 0)
        self.assertEqual({path: path.read_bytes() for path in local_files}, before)
        self.assertFalse((self.root / '.agents/UPSTREAM-SKILLS.i18n.yaml').exists())


if __name__ == '__main__':
    unittest.main()

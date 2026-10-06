# Maintaining bilingual documentation

English | [中文](README.zh.md)

Maintain MyPrivacy documentation in English and Simplified Chinese using the review and checking process below. Either language may be the source of an update. Both files must communicate the same behavior, conditions, limitations, and examples.

<a id="scope-and-file-names"></a>

## Scope and file names

Project-owned Markdown documents form sibling pairs: English `foo.md`, Chinese `foo.zh.md`, and the consistency record `foo.i18n.yaml`. This includes README files, user and developer guides, verification instructions, and `AGENTS.md` instructions.

Local agent materials in the root `.agents/` and `.agent/` directories are excluded from pairing. The [terminology table](terminology.md) is bilingual within one file and also does not require a counterpart. License texts, code, fixtures, generated output, and historical JSON evidence are not translation targets. The checker discovers other project Markdown files automatically, including untracked files.

Each English page links to its Chinese counterpart immediately after its H1 with `English | [中文](foo.zh.md)`. The Chinese page uses `[English](foo.md) | 中文`. Keep one explanation per language rather than placing two full documents in the same file.

<a id="translation-and-review"></a>

## Translation and review

Read the [terminology table](terminology.md) before translating, then review each changed passage using these steps:

1. Read the whole source passage and restate it naturally in the target language.
2. Preserve every actor, action, condition, exception, quantitative limit, and degree of certainty. Add no behavior and omit no limitation.
3. Match heading levels, list kinds and numbering, table structure and row order, emphasis, and physical line counts. Keep one paragraph per physical line.
4. Keep fenced code blocks, their language labels and comments, and inline code byte-identical. Preserve external URLs and non-document paths.
5. Use `.md` links on the English side and `.zh.md` links on the Chinese side for paired documents. Preserve the same query and fragment. Place an identical explicit anchor before every H2 and H3 in both files, using the original source heading’s GitHub slug and blank lines around the anchor.
6. Read the translation on its own for natural phrasing, then compare both sides clause by clause. Only record the pair after this review.

When a pair already exists, translate only the changed passages and preserve unaffected reviewed wording. Rename or remove all three sibling files together. An unresolved term stays in English until the terminology table records a decision; report it as pending rather than silently inventing a translation.

<a id="check-and-record-a-pair"></a>

## Check and record a pair

Run the following commands from the repository root. Python 3.9 or newer is sufficient; the checker uses only the standard library.

```sh
python3 scripts/check-translations.py --list
python3 scripts/check-translations.py README.md
python3 scripts/check-translations.py --write README.md
python3 scripts/check-translations.py
```

The normal check rejects missing counterparts or records, stale hashes, structural mismatches, broken local links, incorrect link locales, malformed language switchers, and whitespace errors. `--list` prints each pair's state without modifying files. `--write` requires explicit pair paths; use `--write --all` only after reviewing every pair. Structural and link checks must pass before records are written.

Records contain the Git-compatible SHA-1 blob hash of both files, keyed by sibling filename. Hashes are computed locally from file bytes; recording does not stage, commit, create Git refs, or upload files. Use ordinary file diffs and version control for future updates.

The gate checks structure and whether the current bytes match the last confirmation. It cannot determine whether a translation is faithful, natural, or factually correct. A passing gate supplements the bilingual review; it does not replace it.

<a id="maintaining-the-checker"></a>

## Maintaining the checker

The checker is owned by [check-translations.py](../../scripts/check-translations.py). Its tests exercise valid pairs and deliberate failures, including missing files, stale records, code changes, wrong-language links, and partial deletion.

```sh
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
```

Changing documentation does not require rerunning plugin execution tests unless the documented runtime behavior also changes. Preserve private configuration outside the repository and use only fictional examples in both languages.

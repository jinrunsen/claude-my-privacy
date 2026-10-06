# Repository guidance

English | [中文](AGENTS.zh.md)

MyPrivacy is a Claude Code plugin for configurable name and company substitution. Read [README.md](README.md) for setup and [docs/user/behavior.md](docs/user/behavior.md) before changing filtering behavior.

<a id="ownership-and-privacy"></a>

## Ownership and privacy

- Production code lives in `plugins/my-privacy/`; `verification/` owns offline CLI fixtures and historical evidence.
- Personal mappings live outside the repository. Never copy actual names, company identifiers, credentials, local transcripts, settings, or private backups into source, examples, tests, documentation, or commits. Use [fictional fixtures](examples/mappings.example.json).
- Preserve best-effort replacement, native tool permissions, and one execution attempt per tool call. Documentation work does not authorize changing these behaviors.
- Source, installed plugin cache, external configuration, and audit storage are separate. Do not update a user's runtime or run `install.py` merely to validate documentation.

<a id="documentation"></a>

## Documentation

For documentation changes, read [docs/AGENTS.md](docs/AGENTS.md) for document ownership, writing rules, and evidence requirements. Keep the changes within the requested scope.

Maintain project documents as English `.md` and Simplified Chinese `.zh.md` pairs. Either language may be the source of an update; update its counterpart and confirm the pair together. Read [docs/i18n/README.md](docs/i18n/README.md) for the bilingual review and Python checks before recording a pair.

<a id="checks"></a>

## Checks

From the repository root:

```sh
npm --prefix plugins/my-privacy test
claude plugin validate --strict .
claude plugin validate --strict plugins/my-privacy
claude plugin test plugins/my-privacy
git diff --check
```

Use `./verification/run.sh` for the isolated macOS CLI regression when runtime behavior or its documented guarantees change. See [verification/README.md](verification/README.md) for prerequisites and limits. Historical runners are not current acceptance gates. Report only checks actually run; do not repeat passing checks without a new reason.

When the repository has untracked files, `git diff --check` does not inspect their content. Include them in manual Markdown, link, and whitespace review without staging them solely for validation.

For documentation changes, run `python3 scripts/check-translations.py`. For changes to that checker, also run `python3 -m unittest discover -s scripts/tests -p 'test_*.py'`. Record confirmed translations with `python3 scripts/check-translations.py --write <pair>` only after comparing both languages for meaning.

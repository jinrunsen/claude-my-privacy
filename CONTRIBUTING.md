# Contributing and verification

English | [中文](CONTRIBUTING.zh.md)

Before making changes, read [AGENTS.md](AGENTS.md) and the affected behavior documentation. All public examples and tests use fictional data; keep real mappings, runtime logs, account configuration, and stable-version backups outside the repository.

<a id="开发环境"></a>

## Development environment

The plain JavaScript tests use Node.js's built-in test runner and require no project dependencies to be installed. Plugin validation and Mod tests require Claude Code with support for the current interfaces; offline CLI regression also requires macOS, Python 3, and `sandbox-exec`. See the [verification guide](verification/README.md) for the exact scope.

Run these commands from the repository root:

```sh
npm --prefix plugins/my-privacy test
claude plugin validate --strict .
claude plugin validate --strict plugins/my-privacy
claude plugin test plugins/my-privacy
```

For changes to tool restoration, session handling, or configuration loading, also run:

```sh
./verification/run.sh
```

Run only checks relevant to the change; do not treat historical probes as current release gates. Host-generated type files and current verification reports are excluded by `.gitignore`.

<a id="documentation"></a>

## Documentation

Documentation is organized by reader task; see [docs/AGENTS.md](docs/AGENTS.md) for writing and evidence rules. Correct the facts owned by the source code before updating the documentation; do not present an inference from a single session as verified behavior.

Check links, anchors, code blocks, and whitespace in changed and new documents, then run `git diff --check`. This command does not check untracked files, so inspect new files separately; empty output does not mean that all documentation has passed.

Use `python3 scripts/check-translations.py` to check all pairs. After reviewing a pair for equivalent meaning, record it with `python3 scripts/check-translations.py --write <pair>`; use `--write --all` only to explicitly record all reviewed pairs. See the [bilingual documentation guide](docs/i18n/README.md) for the pairing rules.

<a id="提交和发布前"></a>

## Before committing and releasing

Inspect the files to be committed and the existing Git history for real names, company identifiers, term lists, credentials, or local machine paths. Ignore rules only prevent some files from being added; they cannot remove content already in history.

For version updates, synchronize the plugin manifest, marketplace entry, `package.json`, and audit version constant; update affected documentation and report the checks actually run. The plugin's default term list must always be empty.

The project is currently `UNLICENSED`. Before a public release, maintainers must choose a project license. Preparing documentation or connecting GitHub does not itself create a remote repository, push, or publish.

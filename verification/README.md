# Verify plugin changes

English | [中文](README.zh.md)

This page is for developers changing the plugin: run the pure-logic and Mod tests first, then use isolated Claude Code sessions to verify local tool execution, text replacement, and subsequent sessions. See the [repository README](../README.md) for installation and everyday use, and the [development architecture](../docs/developer/architecture.md) for implementation details.

<a id="运行当前检查"></a>

## Run the current checks

You need Node.js (including npm), Python 3, and Claude Code with support for `plugin validate` and `plugin test`. Native tool and terminal display regression also require macOS's `/usr/bin/sandbox-exec`. These checks have passed with Claude Code **2.1.290** on macOS; other versions and platforms require fresh verification.

From the repository root, enter the plugin directory and run:

```sh
cd plugins/my-privacy
npm test
claude plugin validate --strict .
claude plugin test .
```

Then return to the repository root to run native tool regression:

```sh
cd ../..
./verification/run.sh
```

[`run.sh`](run.sh) calls [`run-targeted.py`](run-targeted.py). This script is the current execution regression check; you do not need to run the historical probe scripts in this directory.

To check terminal reply display separately, run the optional [`run-display.py`](run-display.py) check from the repository root:

```sh
python3 verification/run-display.py
```

| Check | Passing criteria |
| --- | --- |
| `npm test` | All tests for pure replacement, configuration parsing, content handling, tool policy, and audit pass. |
| `claude plugin validate --strict .` | The plugin manifest and Mod declarations pass validation. |
| `claude plugin test .` | All Mod event tests pass, including display-only reply restoration, preservation of model/session text, fail-open behavior on exceptions, preservation of native errors, and missing configuration. |
| `./verification/run.sh` | The exit code is `0`, the output has `passed` set to `true`, and every item in `checks` is `true`. |
| `python3 verification/run-display.py` | The exit code is `0`, the output has `passed` set to `true`, and every item in `interactive` and `print` is `true`. |

Native tool regression deliberately runs failing commands, reads nonexistent files, and supplies empty, invalid, and unavailable configurations. These are verification scenarios; the check results determine whether the run passes. When platform or CLI prerequisites are missing, the report sets `prerequisitesMissing` and exits with a nonzero status.

<a id="隔离方式与结果"></a>

## Isolation and results

Native tool regression copies the plugin to a private temporary directory, uses a separate `CLAUDE_CONFIG_DIR`, and explicitly sets `CLAUDE_MY_PRIVACY_CONFIG` for every Claude subprocess. [`synthetic_config.py`](synthetic_config.py) supplies fictional person and company mappings; the script does not copy personal mappings, credentials, settings, past sessions, or project files.

A helper Mod supplies fixed model responses, while Claude Code executes the real Bash, Read, Write, and Edit tools. `sandbox-exec` blocks network connections, and the tests use an invalid API key. Native permission checks are skipped only in this temporary test environment with networking disabled; do not enable the helper model Mod in everyday sessions.

The script checks restoration of configured terms in commands and file operations, replacement in text returned by tools, preservation of unrelated text, error messages from native failures, and that tools are not executed again when a session continues or resumes. Empty, invalid, and unavailable configurations must also leave tools usable, introduce no implicit mappings, and report the correct configuration state.

Results contain only derived booleans, counts, and structured states. They are printed to the terminal and saved to `verification/evidence/targeted-latest-summary.json`. Git ignores this report. Temporary sessions, subprocess output, mappings, and test files are cleaned up when the run ends.

The optional display check uses a temporary plugin, fictional mappings, isolated configuration, an invalid API key, and the same network-denying sandbox, with no native tools enabled. It verifies restored text in a real terminal reply, aliases in the next model turn and saved assistant text, and unchanged alias output in headless mode. Only derived checks are retained in the Git-ignored `verification/evidence/display-latest-summary.json`; temporary terminal output and sessions are removed.

If a check fails, first inspect output fields such as `checks`, `timedOut`, `prerequisitesMissing`, and `moduleLoadError` to distinguish assertion failures, timeouts, missing environment prerequisites, and loading failures. Do not substitute an old report for the current run's results.

<a id="验证边界"></a>

## Verification limits

These checks verify message and tool handling visible to the Mod. They do not inspect complete network request bodies or call a real model or remote service. Passing tests does not prove that all requests, logs, or host metadata have been redacted; content such as fixed tool history may still fall outside the Mod's rewriting scope. See [replacement behavior and coverage limits](../docs/user/behavior.md) for details.

Native tool regression uses noninteractive CLI output and does not establish assistant reply restoration in the interactive UI. The optional display check covers a real terminal with fixed fictional replies; plain `--print` output keeps aliases. Mod tests exercise partial and complete text blocks and simulated client properties through `ui.render`, but do not establish real streaming, copy/export, other clients, or cross-block restoration coverage.

<a id="历史探测与归档证据"></a>

## Historical probes and archived evidence

The following scripts preserve earlier investigation methods. They contain expectations for older blocking behavior, generic PII placeholders, or Shell prefix policies, and may fail against the current version. **They are not current acceptance checks.** These scripts also use explicit fictional mapping configurations to avoid falling back to personal mappings.

| Script | Historical purpose |
| --- | --- |
| [`run.py`](run.py) and [`mock-model/`](mock-model/) | Initial text and file replacement, and blocking behavior when saving or resuming sessions. |
| [`run-tools.py`](run-tools.py) | Native optional arguments, Shell prefix parsing, and permission denial; diagnostic mode changes only a temporary plugin copy. |
| [`run-symlinks.py`](run-symlinks.py) | Symlinks for alias directories, Shell separators, and file tools; links are created only in temporary directories. |
| [`run-errors-audit.py`](run-errors-audit.py) | Differences before and after the fix for native error output types, and persistence of audit metadata. |
| [`run-recovery.py`](run-recovery.py) | An unfinished, superseded investigation into recovery. The current policy has no privacy history lock, and `/my-privacy-recover` only provides an explanation. |

Archived JSON in [`evidence/`](evidence/) records observations and counts from that time to trace old policies; it does not represent verification results for the current version. Helper plugins in `mock-model/` are also for testing only.

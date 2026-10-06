# Troubleshooting and local auditing

English | [中文](troubleshooting.zh.md)

First run `/my-privacy-status` to check the version actually loaded, configuration state, and mapping count, then inspect `/my-privacy-audit`. Auditing helps identify the stage at which a failure occurred. It does not store enough content to replay commands and does not change rules automatically.

<a id="常见问题"></a>

## Common problems

Diagnose problems from observable symptoms; avoid inferring execution results solely from redacted output.

| Symptom | Checks and action |
| --- | --- |
| `unavailable` or `invalid` | Check the file's location outside the repository, its readability, and the [configuration format](configuration.md); fix the issue, then reload the plugin |
| `loaded; mappings: 0` | Empty mappings perform no replacement; confirm whether `{"mappings":[]}` is intentional |
| Configuration changes have no effect | Each instance reads configuration only once; run `/reload-plugins`, then check status |
| `COMPLEX_ALIAS_COMMAND`, `AMBIGUOUS_PATH`, or a historical request lock still appears | Distinguish new errors from historical audit records; check the loaded version, plugin copies, and other plugins, then reload. The current policy does not actively generate these blocks |
| A path resolves to an unexpected file | Check whether the alias path actually exists; ordinary file tools prefer an existing alias path, while Bash restores the entire command |
| A domain or account appears not to have been restored | Displayed content may have been redacted again; check the current mappings, whether an old alias is still in use, and the actual target at execution |
| `tool_error` or `Underlying tool ...` | Inspect the native error and local side effects before deciding whether to retry; do not assume that the operation did not execute |

`/my-privacy-recover` only returns compatibility guidance; it does not sanitize the session or execute missed tool calls. The current plugin has no privacy history lock that requires this command to unlock it. To update the plugin, follow the [README](../../README.md#更新).

<a id="审计保存在哪里"></a>

## Where audit records are stored

The plugin stores up to 300 events through Claude Code's `$.store`. With the default configuration directory, storage is located in `~/.claude/plugins/store/`. Use the following pattern to find MyPrivacy files:

```text
~/.claude/plugins/store/my-privacy_my-privacy-marketplace-*.json
```

The asterisk represents a host-assigned suffix, not a literal filename. File locations or names may change when the configuration directory, installation identity, or host version changes. Prefer `/my-privacy-audit` to view the current plugin's records.

The audit records only time, plugin version, tool category, reason code, execution state, and input/output structure. It does not record commands, paths, prompts, tool content, raw exception messages, configuration contents, or credentials. It is neither a log of successful calls nor a network traffic record.

<a id="如何解读一条记录"></a>

## How to interpret a record

The following illustrates the format; it is not an actual run record:

```text
tool_error Bash [result:TOOL_ERROR] execution=unknown; output=object/string; command=81-400, cd=&&, multiline=false, heredoc=false
```

| Field | What it tells you |
| --- | --- |
| `tool_error` | A downstream tool returned an error, rejected the call, or threw an exception; this is not equivalent to a privacy policy block |
| `result:TOOL_ERROR` | A tool error was observed during result processing |
| `execution=unknown` | It is unknown whether execution or side effects occurred |
| `output=object/string` | The outer response is an object whose `result` field is a string; this does not diagnose the root cause |
| `command=81-400` | The command's character count falls within this range; this is not command content |
| `cd=&&` | A structure was detected that starts with `cd` to an absolute path, followed by `&&`; this does not control permissions |
| `multiline`, `heredoc` | Structural indicators of whether the command contains a newline and whether `<<` appears |

Times are output in UTC; the trailing `Z` denotes UTC. `Versions` lists the versions associated with retained events, which do not necessarily match the current plugin version. Descriptions of 0.2.0 in `Analysis` explain historical policy; use `/my-privacy-status` to confirm the current version.

`filter_fallback` means replacement did not complete and the plugin passed through the original content; `CONFIG_UNAVAILABLE` and `CONFIG_INVALID` indicate configuration loading problems. The audit write-failure count belongs only to the current plugin instance and resets on reload.

<a id="能否判断是插件导致的错误"></a>

## Can you tell whether the plugin caused an error?

`tool_error` alone cannot rule out the plugin as a cause: for example, restoring an incorrect path can also cause a native tool error. The audit contains neither the command text nor the actual replacement result, so this record cannot reconstruct what executed at the time.

Reproduce the issue with fictional mappings and minimal input, and separately verify the arguments received by the tool, the result on disk, and the text returned to the model. [Offline verification](../../verification/README.md) demonstrates this approach. When sharing an issue, provide only a redacted minimal reproduction and structural metadata; do not publish private mappings or actual credentials.

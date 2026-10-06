# Replacement behavior and coverage limits

English | [中文](behavior.zh.md)

The plugin lets the model use aliases in supported text while making a best-effort attempt to use real paths and accounts for tools. It replaces specified terms and does not block operations by default; Claude Code's native permissions and other plugins can still reject tool calls.

<a id="输入到执行的流程"></a>

## From input to execution

The table below distinguishes model context, actual tool arguments, and final files. The active mappings come from the [private configuration](configuration.md).

| Content or stage | Plugin behavior |
| --- | --- |
| User-submitted text, supported prompt context, attachment text, and skill prompts | Replace originals with aliases |
| Bash commands and string argument values for ordinary tools | Restore originals from aliases |
| Write content and Edit search and replacement text | Attempt restoration before execution, then pass to the native tool |
| Supported text returned by tools | Replace originals with aliases again |
| Agent, Task, and Skill arguments | Keep aliases for subsequent model use |
| WebFetch | Restore the URL as an execution argument; keep aliases in `prompt` |
| Supported assistant reply display text | Attempt to restore originals only for display |
| Supported text appended to the session | Replace originals with aliases; display restoration does not rewrite this text |

Neither displayed originals nor remaining aliases prove which values a file or network request used. Replaced tool output is not verbatim evidence of the original contents of a local file.

Tool argument object keys and routing fields such as `tool`, `tool_use_id`, and `agentId` remain unchanged. String arguments for unknown MCP tools are restored by default; the plugin cannot tell whether such a tool calls a model internally.

<a id="assistant-reply-display"></a>

## Assistant reply display

Display restoration applies only to assistant text rendered through the host's `AssistantMessage` component. User messages and tool displays are outside this restoration. Each text block is processed independently, so aliases split across blocks may remain. If restoration fails, the host displays the existing text with its aliases.

Restored display text is not written back to stored session text or model context. Those contents remain subject to the same best-effort replacement and coverage limits described below. Plain `--print` output is outside display restoration and keeps aliases. Streaming, copy/export, and other clients have no general restoration guarantee.

<a id="shell-与文件写入"></a>

## Shell commands and file writes

For Bash, the plugin restores literal text across the entire command without parsing, re-quoting, or assembling shell syntax. As a result, `;`, `&&`, pipes, loops, multiline scripts, and heredocs have no special requirements for being allowed through. Restoration also covers scripts and account strings embedded in the command.

This does not mean every mapping preserves command semantics: shell special characters in mapping values may change the execution result. Only aliases present in the command text are restored; the plugin does not recursively rewrite content in the execution environment that the running command reads from environment variables, files, or remote sources.

Text arguments for Write and Edit are restored before execution, and file-writing text embedded in Bash is restored with the command. The plugin does not scan the disk and automatically repair aliases already written to files. A native tool error also does not guarantee that no write occurred.

<a id="路径域名与账号"></a>

## Paths, domains, and accounts

For an explicit `file_path`, `path`, or `notebook_path` supplied to an ordinary tool, the plugin prefers to keep the supplied alias path if it already exists; otherwise, it attempts restoration. An existing path may be a symbolic link or a separate file, and the plugin does not automatically determine the user's intent.

Bash does not check whether an alias path exists before restoring it: alias paths in a command are restored as part of the entire command. The plugin neither creates symbolic links nor depends on them to work.

Domains and accounts are restored as strings, without a domain allowlist, DNS validation, or verification that an account is real. For example, the sample alias `harborwave.example` is restored to `cedarbyte.example` when used as a tool argument. Original values needed for execution reach the target program or service as a consequence of restoring real accounts and network destinations.

After you change aliases, the configuration recognizes only the new mappings; old aliases in existing sessions are not migrated automatically. Re-read the original sources to obtain context with the new aliases, and check the actual target before performing operations with side effects.

<a id="失败与覆盖限制"></a>

## Failures and coverage limits

If replacement fails, the plugin makes a best-effort attempt to pass through the original content and records structural metadata. Each tool call gets only one execution attempt; a failure to replace the result does not trigger a retry. Missing or invalid configuration also passes text through unchanged; see [configuration states](configuration.md#文件位置与加载).

Protection does not cover every input or storage location:

- Unconfigured information remains unchanged; the plugin has no general detection for email addresses, phone numbers, or identity document numbers.
- Images, PDFs, audio, and other unsupported media pass through unchanged, without OCR.
- Signed thinking, fixed tool-call history, system snapshots, raw queues, and file snapshots may retain original values.
- The plugin does not rewrite all historical logs or retract data already sent; old `<PII_...>` placeholders are not restored automatically either.
- Local Claude Code and tools can still read actual files; this plugin cannot fully guarantee protection for other plugins' inputs, network behavior, or logs.

The plugin therefore only reduces exposure of specified terms in supported text. **It cannot guarantee that all requests, displayed content, or logs are redacted**. See the [verification guide](../../verification/README.md) for the scope checked by offline verification.

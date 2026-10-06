# Implementation and data locations

English | [中文](architecture.zh.md)

The plugin separates text replacement, tool execution adaptation, and host event integration. Private configuration is loaded only locally, and Claude Code remains responsible for executing tools. The [replacement guide](../user/behavior.md) defines user-visible behavior; this page helps maintainers locate the implementation they need to change.

Use the bilingual [interactive architecture guide](show-me-architecture.html) to explore the flow through the plugin and the responsibilities of its files.

<a id="模块职责"></a>

## Module responsibilities

The source can be installed as a local marketplace without a build. The root manifest points to `plugins/my-privacy/`, and the plugin's hooks manifest loads the registration entry point.

| File | Responsibility |
| --- | --- |
| [marketplace.json](../../.claude-plugin/marketplace.json) | Declares the local marketplace and plugin source |
| [plugin.json](../../plugins/my-privacy/.claude-plugin/plugin.json) | Plugin name, version, and license status |
| [hooks/register.js](../../plugins/my-privacy/hooks/register.js) | Loads configuration, handles prompt, session, and reply display events, executes tools, and records audit events |
| [lib/privacy.js](../../plugins/my-privacy/lib/privacy.js) | Pure replacement engine with case handling and resource limits, but no built-in personal term list |
| [lib/configuration.js](../../plugins/my-privacy/lib/configuration.js) | Parses external JSON and validates term lists |
| [lib/tool-policy.js](../../plugins/my-privacy/lib/tool-policy.js) | Separates execution arguments from model arguments and handles existing alias paths |
| [lib/content.js](../../plugins/my-privacy/lib/content.js) | Handles messages and tool results while preserving protocol fields and opaque media |
| [lib/audit.js](../../plugins/my-privacy/lib/audit.js) | Generates and validates structural metadata and outputs fixed diagnostic recommendations |

<a id="加载与调用"></a>

## Loading and calls

Configuration is loaded lazily once per plugin instance; a shared loading Promise avoids duplicate concurrent reads. Read or parse failures leave an empty replacer in place and record a fixed reason code. Reloading the plugin creates a new configuration state.

Event handling first replaces terms in supported prompt text. The tool call adapter restores execution arguments, calls the downstream handler exactly once, then replaces terms in the returned text. Downstream errors return through the error channel, avoiding an error string being presented as a normal tool result where an object is required; failures in result handling do not replay the tool.

Session append, compaction, and send events each process the fields that the host allows them to rewrite. Fixed history and signature fields cannot be arbitrarily rewritten for redaction, so these event handlers do not filter the entire model request or all persisted records.

The `ui.render` handler uses `privacy.restore` to restore only `AssistantMessage` text and forwards the changed `props.text` through `next` for native rendering, preserving other rendering properties. It does not mutate session or model content or restore `UserMessage` and tool displays. Each block is independent; if restoration fails, native rendering receives the unchanged text. See [reply display limits](../user/behavior.md#assistant-reply-display).

<a id="四类本地数据"></a>

## Four kinds of local data

These locations serve different purposes and are not interchangeable:

| Data | Location and maintenance |
| --- | --- |
| Source, fictional examples, and tests | This repository; managed by Git |
| Installed runtime copy | Claude Code plugin cache; refreshed through the plugin update command |
| Private term list | JSON outside the repository; see the [configuration guide](../user/configuration.md) for location and loading rules |
| Diagnostic events | Host plugin storage; see the [troubleshooting guide](../user/troubleshooting.md) for the format and how to view it |

Source changes do not automatically refresh an already-loaded runtime copy; changes to private configuration do not automatically refresh existing instances. Development tests use fictional configuration and must not depend on a maintainer's personal environment.

<a id="安装辅助脚本"></a>

## Installation helper script

[install.py](../../install.py) contains deployment conventions for the local machine and is not required for routine installation. The script uses `~/.local/bin/claude`, checks the minimum version, validates and registers the plugin, then backs up and modifies settings under the default `~/.claude` directory.

It requests that this plugin be ordered first, disables an enabled `fast-jev-compaction@fast-jev-compaction`, sets telemetry-related environment variables, and adjusts permissions on the source directory and some cache files. Backups are stored outside the repository at `~/.local/state/claude-my-privacy/`. Managed policy may not honor user-level plugin ordering settings.

The script's code defines these side effects; it has not been rerun against real user configuration for documentation verification. Use the CLI flow in the [README](../../README.md#安装并验证) for routine installation.

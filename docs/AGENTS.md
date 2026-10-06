# Documentation conventions

English | [中文](AGENTS.zh.md)

Before editing, identify the reader's task and the page that owns its explanation. Update that page and link to it from other documents that need the same facts.

<a id="document-ownership"></a>

## Document ownership

Maintain project-owned documentation in English and Simplified Chinese using the [bilingual workflow](i18n/README.md). Organize each page around its reader's task; add headings and navigation where they help the reader complete that task.

The documentation owners are:

| Reader task | Owner |
| --- | --- |
| Understand the plugin, install it, verify it is active | [README.md](../README.md) |
| Define mappings and understand configuration states | [user/configuration.md](user/configuration.md) |
| Understand replacement, execution, replies, and limits | [user/behavior.md](user/behavior.md) |
| Diagnose errors and interpret audit metadata | [user/troubleshooting.md](user/troubleshooting.md) |
| Change implementation and locate responsibilities | [developer/architecture.md](developer/architecture.md) |
| Develop and prepare changes for review | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Run offline verification and interpret historical evidence | [verification/README.md](../verification/README.md) |
| Maintain translations and terminology | [i18n/README.md](i18n/README.md) |

<a id="writing-and-evidence"></a>

## Writing and evidence

Begin with the reader's outcome and the material limitation. Put prerequisites before commands, explain observable success, and give a recovery path. Preserve actors, actions, conditions, failure behavior, exceptions, and uncertainty when shortening text.

Verify claims against implementation and focused tests. Exercise commands in an isolated fixture when they change configuration; never use live account data as a documentation test. If an interactive or external operation was not exercised, say so in the verification report rather than claiming success.

Use relative Markdown links for local files. Preserve current behavior in user guides; historical policy and probe results belong in the verification documentation. Do not hand-edit evidence JSON to make it appear current. Do not copy session troubleshooting transcripts into durable docs.

Each English `foo.md` has a Chinese `foo.zh.md` and a `foo.i18n.yaml` consistency record. Add reciprocal language switchers, preserve code blocks and inline code verbatim, and keep section structure and physical line counts aligned. Local document links follow the reader's language while preserving their target and fragment. Follow [terminology.md](i18n/terminology.md) and review meaning before recording hashes; a structural check cannot certify translation quality.

Before completion, check local links and anchors, fenced code, trailing whitespace, and final newlines across changed and new files. Run the relevant checks in [AGENTS.md](../AGENTS.md). Record any unavailable check and its practical limitation. Source code and plugin-visible strings are outside a documentation-only edit.

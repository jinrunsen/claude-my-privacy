# Terminology / 术语表

This bilingual table defines MyPrivacy terminology. It follows the [pinned upstream terminology](https://github.com/deepseek-ai/deepseek-harness/blob/00102833dfaee1da9f48a3a8eae9d34005a75218/docs/i18n/terminology.md) for shared terms and records the project's existing privacy terminology. Use the Chinese column in Chinese prose and the English column in English prose. Keep product names, commands, identifiers, paths, and all code spans verbatim. This file is bilingual by construction and has no counterpart.

本双语表定义 MyPrivacy 的术语。通用术语遵循[固定版本的上游术语表](https://github.com/deepseek-ai/deepseek-harness/blob/00102833dfaee1da9f48a3a8eae9d34005a75218/docs/i18n/terminology.md)，隐私相关术语沿用本项目现有用法。中文正文使用「中文」列，英文正文使用「English」列。产品名、命令、标识符、路径和所有行内代码均保留原文。本文件自成双语，不另设对侧文件。

| English | 中文 | First occurrence / 首次出现 | Usage / 用法 |
| --- | --- | --- | --- |
| agent | agent | agent（智能体） | Keep English in Chinese prose. / 中文正文保留英文。 |
| skill | skill | skill（技能） | Keep English in Chinese prose. / 中文正文保留英文。 |
| plugin | 插件 | | |
| session | 会话 | | |
| tool | 工具 | | |
| native tool | 原生工具 | | |
| tool call | 工具调用 | | |
| tool result | 工具结果 | | |
| hook | 钩子 | | |
| prompt | 提示词 | | |
| system prompt | 系统提示词 | | |
| message | 消息 | | |
| context | 上下文 | | |
| runtime | 运行时 | | |
| transcript | transcript | transcript（文本记录） | A rendered conversation record, distinct from an event log. / 会话的呈现文本，区别于事件日志。 |
| monorepo | monorepo | | Keep English in Chinese prose. / 中文正文保留英文。 |
| permission | 权限 | | |
| configuration | 配置 | | |
| config key | 配置键 | | |
| private configuration | 私有配置 | | |
| alias | 化名 | | A replacement name, distinct from a command alias. / 替换后的名称，区别于命令别名。 |
| mapping | 映射 | | A configured original-to-alias relationship. / 配置中的原文与化名对应关系。 |
| redaction | 脱敏 | | Replacing configured sensitive text with aliases. / 将配置中的敏感文本替换为化名。 |
| restoration | 恢复 | | Replacing aliases with their configured original text. / 将化名替换回配置中的原文。 |
| best-effort | 尽力 | | Preserve the stated limitations; do not imply a guarantee. / 保留原文限制，不得改写为保证。 |
| fallback (return original content) | 失败时返回原文 | | Fail-open filtering behavior; do not confuse with configuration lookup. / 指过滤失败时放行原文的行为，不得与配置查找混淆。 |
| fallback (configuration path) | 回退路径 | | An alternative path used during configuration lookup. / 查找配置时使用的备选路径。 |
| audit event | 审计事件 | | |
| event | 事件 | | |
| event log | 事件日志 | | |
| workflow | 工作流 | | |
| fixture | fixture | fixture（测试前置数据） | Keep English in Chinese prose. / 中文正文保留英文。 |
| mock | mock | | Keep English in Chinese prose. / 中文正文保留英文。 |
| CLI | CLI | CLI（命令行界面） | |
| PR | PR | PR（Pull Request） | |
| API | API | | |
| MCP | MCP | | |
| JSONL | JSONL | | |
| LLM | LLM | LLM（大语言模型） | |
| schema | schema | | Keep English in Chinese prose. / 中文正文保留英文。 |
| smoke test | 冒烟测试 | | |
| snapshot | 快照 | | |
| source of truth | 真源 | | |
| counterpart | 对侧文件 | | Bilingual documentation. / 双语文档语境。 |
| pairing | 配对 | | |
| contract | 约定 | | |
| language switcher | 语言切换行 | | |
| fenced code block | 围栏代码块 | | |
| structural signature | 结构签名 | | |
| sidecar file | 伴随文件 | | |
| sidecar record | 伴随记录 | | |
| blob hash | blob hash | | Keep English in Chinese prose. / 中文正文保留英文。 |
| quality gate | 质量门禁 | | |
| stale | 陈旧 | | Use for translation state, not expiration. / 指译文同步状态，不指到期。 |
| merge | 合并 | | |
| package | 包 | | |
| subagent | subagent | | Keep English in Chinese prose. / 中文正文保留英文。 |
| frontmatter | frontmatter | | Pending; tentative Chinese: 文档头部元数据. Not adopted; retain English. / 待定；候选译法为「文档头部元数据」，尚未采用，正文保留英文。 |
| stacked-PR | stacked-PR | | Pending; tentative Chinese: 堆叠 PR. Not adopted; retain English. / 待定；候选译法为「堆叠 PR」，尚未采用，正文保留英文。 |
| GitHub slug | GitHub slug | | Pending; tentative Chinese: GitHub 锚点名. Not adopted; retain English. / 待定；候选译法为「GitHub 锚点名」，尚未采用，正文保留英文。 |

Apply first-occurrence glosses once per document, only in Chinese prose. A gloss within a compound also covers the contained term. Protected code is never glossed or translated. Preserve canonical spelling for MyPrivacy, Claude Code, DeepSeek Harness, GitHub, Python, Node.js, and Cordis. For an undecided technical term, retain English and report it as pending; add an agreed rendering here before using it throughout the documents.

首次出现的括注仅用于中文正文，每篇文档只加一次；组合词中的括注也覆盖其中的单个术语。受保护的代码不得加括注或翻译。MyPrivacy、Claude Code、DeepSeek Harness、GitHub、Python、Node.js 和 Cordis 均保留规范拼写。尚未确定译法的技术术语保留英文，并在报告中列为待定术语；确定后先补入本表，再在文档中统一使用。

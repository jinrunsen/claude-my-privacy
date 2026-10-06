# 文档规范

[English](AGENTS.md) | 中文

修改前，先确定读者的任务及负责解释该任务的页面。更新负责页面，并从需要相同事实的其他文档链接到该页面。

<a id="document-ownership"></a>

## 文档职责

按[双语工作流](i18n/README.zh.md)以英文和简体中文维护项目自有文档。围绕读者任务组织各页面；在有助于读者完成任务的位置添加标题和导航。

各类文档的职责如下：

| 读者任务 | 负责文档 |
| --- | --- |
| 了解插件、完成安装并验证是否生效 | [README.md](../README.zh.md) |
| 定义映射并了解配置状态 | [user/configuration.md](user/configuration.zh.md) |
| 了解替换、执行、回复和限制 | [user/behavior.md](user/behavior.zh.md) |
| 诊断错误并解读审计元数据 | [user/troubleshooting.md](user/troubleshooting.zh.md) |
| 修改实现并确定职责归属 | [developer/architecture.md](developer/architecture.zh.md) |
| 开发并准备待审查的变更 | [CONTRIBUTING.md](../CONTRIBUTING.zh.md) |
| 运行离线验证并解读历史证据 | [verification/README.md](../verification/README.zh.md) |
| 维护翻译和术语 | [i18n/README.md](i18n/README.zh.md) |

<a id="writing-and-evidence"></a>

## 写作与证据

开篇说明读者要达成的结果和实质性限制。先说明前置条件，再给出命令，解释可观察的成功结果，并提供恢复路径。精简文字时，保留执行主体、动作、条件、失败行为、例外和不确定性。

依据实现和专项测试核实表述。会更改配置的命令应在隔离的 fixture（测试前置数据）中验证；禁止使用真实账户数据测试文档。未验证交互操作或外部操作时，应在验证报告中明确说明，不得声称成功。

本地文件使用相对 Markdown 链接。用户指南描述当前行为；历史策略和探测结果放在验证文档中。不得手改证据 JSON，使其看似反映当前状态。不得将会话中的故障排查 transcript（文本记录）复制到长期维护的文档中。

每个英文 `foo.md` 均有中文 `foo.zh.md` 和 `foo.i18n.yaml` 一致性记录。添加相互链接的语言切换行，逐字保留代码块和行内代码，并保持章节结构和物理行数一致。本地文档链接应使用读者的语言，同时保留目标和片段。遵循 [terminology.md](i18n/terminology.md)，记录哈希前先核对含义；结构检查无法证明翻译质量。

完成前，检查所有变更和新增文件中的本地链接与锚点、围栏代码、行尾空格和文件末尾换行。运行 [AGENTS.md](../AGENTS.zh.md) 中的相关检查。记录无法执行的检查及其实际限制。仅修改文档时，不涉及源码和插件可见字符串。

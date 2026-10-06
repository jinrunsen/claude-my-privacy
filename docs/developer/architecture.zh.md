# 实现与数据位置

[English](architecture.md) | 中文

插件把文本替换、工具执行适配和宿主事件接入分开。私有配置只在本地加载，工具执行仍由 Claude Code 负责。用户可见的行为以[替换说明](../user/behavior.zh.md)为准；本页帮助维护者找到需要修改的实现。

通过双语[交互式架构指南](show-me-architecture.html)了解插件中的处理流程和各文件的职责。

<a id="模块职责"></a>

## 模块职责

源码无需构建即可作为本地 marketplace 安装。根目录清单指向 `plugins/my-privacy/`，插件的 hooks 清单加载注册入口。

| 文件 | 职责 |
| --- | --- |
| [marketplace.json](../../.claude-plugin/marketplace.json) | 声明本地 marketplace 和插件来源 |
| [plugin.json](../../plugins/my-privacy/.claude-plugin/plugin.json) | 插件名称、版本和许可证状态 |
| [hooks/register.js](../../plugins/my-privacy/hooks/register.js) | 加载配置、接入提示、会话和回复显示事件、执行工具、记录审计 |
| [lib/privacy.js](../../plugins/my-privacy/lib/privacy.js) | 无内置个人词表的纯替换引擎、大小写和资源限制 |
| [lib/configuration.js](../../plugins/my-privacy/lib/configuration.js) | 外部 JSON 格式解析与词表校验 |
| [lib/tool-policy.js](../../plugins/my-privacy/lib/tool-policy.js) | 区分执行参数和模型参数，处理现存化名路径 |
| [lib/content.js](../../plugins/my-privacy/lib/content.js) | 处理消息和工具结果，保留协议字段与不透明媒体 |
| [lib/audit.js](../../plugins/my-privacy/lib/audit.js) | 生成和校验结构元数据，输出固定诊断建议 |

<a id="加载与调用"></a>

## 加载与调用

配置在插件实例中惰性加载一次，共享加载 Promise 避免并发重复读取。读取或解析失败时保留空替换器，并记录固定原因码。重新加载插件创建新的配置状态。

事件处理先替换支持的提示文本。工具调用适配器恢复执行参数，只调用一次下游处理器，然后替换返回文本。下游错误通过错误通道返回，避免将错误字符串伪装为要求对象的正常工具结果；结果处理失败时不重放工具。

会话追加、压缩和发送各自处理宿主允许重写的字段。固定历史和签名字段不能因为需要脱敏就任意改写，因此这些事件处理不是整个模型请求或全部持久化记录的过滤器。

`ui.render` 处理器仅通过 `privacy.restore` 恢复 `AssistantMessage` 文本，将改写后的 `props.text` 经由 `next` 交给原生渲染，并保留其他渲染属性。它不修改会话或模型内容，也不恢复 `UserMessage` 和工具显示。各文本块独立处理；恢复失败时，原生渲染接收未改写的文本。详见[回复显示限制](../user/behavior.zh.md#assistant-reply-display)。

<a id="四类本地数据"></a>

## 四类本地数据

这些位置用途不同，不能互相替代：

| 数据 | 所在位置和维护方式 |
| --- | --- |
| 源码、虚构示例和测试 | 本仓库；由 Git 管理 |
| 安装后的运行副本 | Claude Code 插件缓存；通过插件更新命令刷新 |
| 私有词表 | 仓库外的 JSON；位置与加载规则见[配置说明](../user/configuration.zh.md) |
| 诊断事件 | 宿主插件存储；格式与查看方法见[排障说明](../user/troubleshooting.zh.md) |

修改源码不会自动刷新已经加载的运行副本；修改私有配置不会自动刷新现有实例。开发测试使用虚构配置，不能依赖维护者的个人环境。

<a id="安装辅助脚本"></a>

## 安装辅助脚本

[install.py](../../install.py)包含本机部署约定，不是常规安装必需步骤。脚本使用 `~/.local/bin/claude`，检查最低版本、验证并注册插件，随后备份和修改默认 `~/.claude` 下的设置。

它会请求将本插件排在前面、停用已启用的 `fast-jev-compaction@fast-jev-compaction`、设置遥测相关环境变量，并调整源码目录和部分缓存文件权限。备份保存在仓库外的 `~/.local/state/claude-my-privacy/`。托管策略可能不采纳用户级插件顺序设置。

这些副作用由脚本代码定义，未作为文档验证在真实用户配置上重跑。常规安装使用 [README](../../README.zh.md#安装并验证)中的 CLI 流程。

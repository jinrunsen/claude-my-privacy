# MyPrivacy

[English](README.md) | 中文

在 Claude Code 支持的模型输入文本中，将指定姓名和公司信息替换为化名；执行本地工具前恢复原文，再对工具返回文本做替换。插件也尝试在支持的助手回复显示中将化名恢复为原文。插件采用尽力替换策略，不设置命令或邮箱白名单，不因替换失败锁住会话。

**它只处理配置中的词，不是通用 PII 检测器。** 未配置的信息和不支持的内容可能保留原文。源码不内置个人映射，插件本身不调用模型或网络检测服务。[替换范围与限制](docs/user/behavior.zh.md)说明了哪些内容受保护、哪些内容会恢复。

当前插件版本为 **0.5.0**。离线工具与终端显示检查已在 macOS、Claude Code **2.1.290** 上通过；其他版本和平台需要重新验证。已检查的范围见[验证说明](verification/README.zh.md)。

仓库名为 `claude-my-privacy`，安装标识为 `my-privacy@my-privacy-marketplace`，命令统一使用 `/my-privacy-` 前缀。

<a id="安装并验证"></a>

## 安装并验证

以下命令从本仓库根目录运行。先确认 `claude` 命令可用；开发和离线验证的额外依赖见[贡献指南](CONTRIBUTING.zh.md)。

<a id="1-创建私有配置"></a>

### 1. 创建私有配置

将虚构示例复制到仓库外，再编辑为自己的映射。已有文件不会被下面的复制命令覆盖。

```sh
mkdir -p "$HOME/.config/claude-my-privacy"
chmod 700 "$HOME/.config/claude-my-privacy"
if [ ! -e "$HOME/.config/claude-my-privacy/mappings.json" ]; then
  cp -n examples/mappings.example.json "$HOME/.config/claude-my-privacy/mappings.json"
fi
chmod 600 "$HOME/.config/claude-my-privacy/mappings.json"
```

[示例配置](examples/mappings.example.json)使用陈星河 → 陈瑞恩、`chenxinghe` → `ryanchen`、云杉智科 → 海岚数科、`cedarbyte` → `harborwave`。**请只在仓库外填写真实信息。** 配置格式、大小写和化名选择见[配置说明](docs/user/configuration.zh.md)。

<a id="2-安装插件"></a>

### 2. 安装插件

将本目录登记为本地 marketplace，然后安装插件：

```sh
claude plugin marketplace add "$PWD" --scope user
claude plugin install my-privacy@my-privacy-marketplace --scope user
```

<a id="3-确认配置生效"></a>

### 3. 确认配置生效

在 Claude Code 会话中运行：

```text
/reload-plugins
/my-privacy-status
```

成功加载非空配置时，状态包含 `Configuration: loaded` 和大于零的 `mappings` 数量。`loaded; mappings: 0` 表示空词表；`unavailable` 或 `invalid` 表示没有启用替换。[排障说明](docs/user/troubleshooting.zh.md)提供对应处理步骤。状态命令不展示词表，插件不常驻状态栏。

<a id="日常使用"></a>

## 日常使用

正常输入需求和调用工具即可。例如，示例配置会把模型侧的 `staff42@harborwave.example` 恢复为工具实际使用的 `staff42@cedarbyte.example`。支持的助手回复显示会尝试呈现原文，不改写已存储的会话文本或模型上下文。通过 Write、Edit 或 Bash 写入文件的执行参数也会尝试恢复。[查看完整流程与显示限制](docs/user/behavior.zh.md)。

修改私有配置后运行 `/reload-plugins`，再检查 `/my-privacy-status`。插件每次加载只读取一次配置。诊断使用 `/my-privacy-audit`，其中只保留结构元数据，不保存命令或正文。

<a id="更新"></a>

## 更新

源码更新并增加插件版本号后，在终端执行：

```sh
claude plugin update my-privacy@my-privacy-marketplace --scope user
```

随后在运行中的会话执行 `/reload-plugins` 和 `/my-privacy-status`。源码目录是 marketplace 的安装来源；运行副本在 Claude 插件缓存中。移动源码目录后，需要重新登记 marketplace 路径。

`install.py` 会额外修改插件顺序、停用指定压缩插件并写入遥测相关设置。常规安装使用上面的 CLI 命令；脚本的副作用见[开发说明](docs/developer/architecture.zh.md#安装辅助脚本)。

<a id="文档与开发"></a>

## 文档与开发

按任务选择文档，不必阅读全部实现：

| 任务 | 文档 |
| --- | --- |
| 配置姓名、公司、域名和邮箱中的词 | [配置说明](docs/user/configuration.zh.md) |
| 理解输入、工具执行、文件和回复的区别 | [替换行为与边界](docs/user/behavior.zh.md) |
| 排查路径、旧拦截信息和工具错误 | [排障与审计](docs/user/troubleshooting.zh.md) |
| 定位实现、加载和存储职责 | [架构说明](docs/developer/architecture.zh.md) |
| 修改代码、检查文档和准备发布 | [贡献指南](CONTRIBUTING.zh.md) |
| 运行隔离验证、查阅历史探针 | [验证说明](verification/README.zh.md) |

当前项目尚未授予开源许可证，插件清单标记为 `UNLICENSED`。

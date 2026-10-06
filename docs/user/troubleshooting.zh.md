# 排障与本地审计

[English](troubleshooting.md) | 中文

先运行 `/my-privacy-status` 确认实际加载的版本、配置状态和映射数量，再查看 `/my-privacy-audit`。审计帮助识别失败发生在哪一阶段，不保存足以重放命令的内容，也不会自动修改规则。

<a id="常见问题"></a>

## 常见问题

按可观察到的现象定位问题，避免仅凭脱敏后的显示内容推断执行结果。

| 现象 | 检查与处理 |
| --- | --- |
| `unavailable` 或 `invalid` | 检查仓库外的文件位置、可读性及[配置格式](configuration.zh.md)，修正后重新加载插件 |
| `loaded; mappings: 0` | 空词表不会替换；确认是否有意使用 `{"mappings":[]}` |
| 修改配置后没有变化 | 每个实例只读取一次配置；运行 `/reload-plugins`，再检查状态 |
| 仍出现 `COMPLEX_ALIAS_COMMAND`、`AMBIGUOUS_PATH` 或历史请求锁 | 区分新错误与审计中的历史记录；核对加载版本、插件副本和其他插件，并重新加载。当前策略不主动生成这些拦截 |
| 路径命中了意外文件 | 检查化名路径是否确实存在；普通文件工具优先使用现存化名路径，Bash 则做整条命令恢复 |
| 域名或账号似乎没有恢复 | 显示内容可能已再次脱敏；检查当前词表、是否仍使用旧化名，以及执行端的实际目标 |
| `tool_error` 或 `Underlying tool ...` | 查看原生错误和本地副作用，再决定是否重试；不要假设操作一定未执行 |

`/my-privacy-recover` 只返回兼容说明，不清洗会话、不补执行工具。当前插件没有需要该命令解锁的隐私历史锁。需要更新插件时，按 [README](../../README.zh.md#更新)操作。

<a id="审计保存在哪里"></a>

## 审计保存在哪里

插件通过 Claude Code 的 `$.store` 保存最多 300 条事件。默认配置目录下，存储位于 `~/.claude/plugins/store/`，可按以下模式查找 MyPrivacy 的文件：

```text
~/.claude/plugins/store/my-privacy_my-privacy-marketplace-*.json
```

星号表示宿主分配的后缀，不是字面文件名。变更配置目录、安装身份或宿主版本后，文件位置或名称也可能改变。优先用 `/my-privacy-audit` 查看当前插件的记录。

审计只记录时间、插件版本、工具类别、原因码、执行状态及输入输出结构。不记录命令、路径、提示词、工具正文、异常原文、配置内容或凭据。它不是成功调用流水，也不是网络流量记录。

<a id="如何解读一条记录"></a>

## 如何解读一条记录

以下是格式示意，不是运行记录：

```text
tool_error Bash [result:TOOL_ERROR] execution=unknown; output=object/string; command=81-400, cd=&&, multiline=false, heredoc=false
```

| 字段 | 能说明什么 |
| --- | --- |
| `tool_error` | 下游工具返回错误、拒绝或抛出异常；不等同于隐私策略拦截 |
| `result:TOOL_ERROR` | 在结果处理阶段观察到工具错误 |
| `execution=unknown` | 无法确定是否执行或产生副作用 |
| `output=object/string` | 外层响应为对象，其 `result` 字段为字符串；不是错误根因诊断 |
| `command=81-400` | 命令字符数落在此区间，不是命令内容 |
| `cd=&&` | 检测到以绝对路径 `cd` 开头并接 `&&` 的结构；不控制权限 |
| `multiline`、`heredoc` | 命令是否含换行、是否出现 `<<` 的结构特征 |

时间以 UTC 输出，末尾 `Z` 表示 UTC。`Versions` 是保留事件各自的版本，不一定等于当前插件版本。`Analysis` 中有关 0.2.0 的描述是对历史策略的说明，应以 `/my-privacy-status` 确认当前版本。

`filter_fallback` 表示替换未完成，插件放行原内容；`CONFIG_UNAVAILABLE`、`CONFIG_INVALID` 指向配置加载问题。审计写入失败计数仅属于当前插件实例，重新加载后重置。

<a id="能否判断是插件导致的错误"></a>

## 能否判断是插件导致的错误

仅凭 `tool_error` 不能断定与插件无关：例如，恢复到错误的路径也可能让原生工具报错。审计没有命令正文和实际替换结果，无法从这条记录还原当时执行了什么。

使用虚构映射和最小输入复现，分别确认工具收到的参数、磁盘上的结果以及模型侧返回文本。[离线验证](../../verification/README.zh.md)展示了这种检查方式。分享问题时只提供脱敏后的最小复现和结构元数据；不要公开私有词表或真实凭据。

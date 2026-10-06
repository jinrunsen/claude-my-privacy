# 配置姓名与公司替换

[English](configuration.md) | 中文

每组映射定义一个原文和一个化名。插件将支持文本中的原文替换为化名，并在可执行工具参数中反向恢复。请为自己的姓名、公司中文名和英文标识分别配置条目；插件不会推断它们之间的关系。

<a id="文件位置与加载"></a>

## 文件位置与加载

默认配置文件是 `~/.config/claude-my-privacy/mappings.json`，位于源码和插件缓存之外。首次创建步骤见 [README](../../README.zh.md#安装并验证)。也可以在启动 Claude Code 前，将 `CLAUDE_MY_PRIVACY_CONFIG` 设置为其他配置文件的绝对路径。

显式指定的路径无法读取时，插件不会退回默认文件。每个插件实例只加载一次配置；修改后运行 `/reload-plugins` 和 `/my-privacy-status`。

| 状态 | 含义 | 替换行为 |
| --- | --- | --- |
| `loaded`，数量大于零 | 文件读取及校验成功 | 使用指定词表 |
| `loaded`，数量为零 | 配置为 `{"mappings":[]}` | 原样通过 |
| `unavailable` | 路径不符合要求或文件无法读取 | 原样通过，记录 `CONFIG_UNAVAILABLE` |
| `invalid` | JSON 或词表校验失败 | 原样通过，记录 `CONFIG_INVALID` |

状态和审计不输出配置正文。文件权限由使用者管理，插件不会强制校验 `600` 权限；真实配置应保留在私有目录内。

<a id="配置格式"></a>

## 配置格式

顶层只接受 `mappings` 数组。以下都是虚构名称；完整样例见 [mappings.example.json](../../examples/mappings.example.json)。

```json
{
  "mappings": [
    { "from": "陈星河", "to": "陈瑞恩" },
    {
      "from": "chenxinghe",
      "to": "ryanchen",
      "casePairs": [{ "from": "ChenXingHe", "to": "RyanChen" }]
    },
    { "from": "云杉智科", "to": "海岚数科" },
    { "from": "cedarbyte", "to": "harborwave" }
  ]
}
```

`from` 是需要保护的原文，`to` 是模型使用的化名。可选的 `casePairs` 只指定同一组词的精确大小写形式，不添加其他别名。对应条目的大小写完全匹配时优先使用 `casePairs`。

<a id="匹配规则"></a>

## 匹配规则

匹配是**不区分大小写的字面子串替换，没有单词边界**。配置中的词会在路径、域名、邮箱及较长单词内部命中；字符不会按正则表达式解释。

| 输入 | 模型侧结果 |
| --- | --- |
| `/Users/chenxinghe/Downloads/sase.cedarbyte.example_nginx` | `/Users/ryanchen/Downloads/sase.harborwave.example_nginx` |
| `staff42@cedarbyte.example` | `staff42@harborwave.example` |
| `mycedarbytecache` | `myharborwavecache` |
| `other.person@example.test` | 保持原样 |

未配置的短标识符保持原样。**如果显式配置短缩写，它也会在其他单词内部命中**，因此应避免使用容易碰撞的短词。域名和邮箱没有单独的白名单，也不会自动隐藏邮箱本地部分、手机号或证件号。

全大写、全小写和首字母大写使用相应形式恢复；其他混合大小写采用字符位置推导，不保证精确往返。对大小写敏感的路径或账号，应配置并验证 `casePairs`。

<a id="化名选择与校验"></a>

## 化名选择与校验

化名是保留词。工具参数中出现它时，插件无法判断它是在指代原文，还是现实中恰好同名的账号、域名或文件。选择未在工作环境中使用的化名，并用虚构数据验证往返。[行为说明](behavior.zh.md#路径域名与账号)解释了路径例外。

不要选用会改变 Shell 含义的映射值。插件不会为替换后的空格、引号、美元符号或其他 Shell 特殊字符自动转义，也不校验化名是否适合某个账号或域名格式。

配置解析会拒绝以下情况：

- 未知字段、非法 JSON、空白词或忽略大小写后相同的原文与化名。
- 多组原文之间、化名之间或原文与化名之间存在重复或子串包含冲突。
- 重复或不属于本组词的 `casePairs`；包含保留标记 `<PII_` 的映射。
- 超过 262144 个 JavaScript 字符单位、256 组映射、每组 32 对大小写变体，或单个词超过 500 个字符单位。

校验失败时整个配置不启用，不会只加载部分条目。限制和校验的实现分别由 [configuration.js](../../plugins/my-privacy/lib/configuration.js) 与 [privacy.js](../../plugins/my-privacy/lib/privacy.js)维护。

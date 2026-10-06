# Configure name and company replacement

English | [中文](configuration.zh.md)

Each mapping defines an original value and an alias. The plugin replaces the original with the alias in supported text and restores the original in tool arguments used for execution. Configure separate entries for your name, your company's Chinese name, and its English identifier; the plugin does not infer relationships between them.

<a id="文件位置与加载"></a>

## File location and loading

The default configuration file is `~/.config/claude-my-privacy/mappings.json`, outside the source tree and plugin cache. See the [README](../../README.md#安装并验证) for initial setup. You can also set `CLAUDE_MY_PRIVACY_CONFIG` to the absolute path of another configuration file before starting Claude Code.

If an explicitly specified path cannot be read, the plugin does not fall back to the default file. Each plugin instance loads its configuration only once; after making changes, run `/reload-plugins` and `/my-privacy-status`.

| State | Meaning | Replacement behavior |
| --- | --- | --- |
| `loaded`, count greater than zero | File read and validation succeeded | Use the specified mappings |
| `loaded`, count zero | Configuration is `{"mappings":[]}` | Pass through unchanged |
| `unavailable` | The path does not meet the requirements or the file cannot be read | Pass through unchanged and record `CONFIG_UNAVAILABLE` |
| `invalid` | JSON or mapping validation failed | Pass through unchanged and record `CONFIG_INVALID` |

Status and audit output do not include configuration contents. You manage file permissions; the plugin does not enforce `600` permissions. Keep your actual configuration in a private directory.

<a id="配置格式"></a>

## Configuration format

Only a `mappings` array is accepted at the top level. All names below are fictional; see [mappings.example.json](../../examples/mappings.example.json) for the complete example.

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

`from` is the original value to protect, and `to` is the alias used by the model. The optional `casePairs` specifies only exact capitalization variants of the same pair of terms; it does not add other aliases. A `casePairs` entry takes precedence when its capitalization matches exactly.

<a id="匹配规则"></a>

## Matching rules

Matching uses **case-insensitive literal substring replacement, without word boundaries**. Configured terms match inside paths, domains, email addresses, and longer words; characters are not interpreted as regular expressions.

| Input | Model-side result |
| --- | --- |
| `/Users/chenxinghe/Downloads/sase.cedarbyte.example_nginx` | `/Users/ryanchen/Downloads/sase.harborwave.example_nginx` |
| `staff42@cedarbyte.example` | `staff42@harborwave.example` |
| `mycedarbytecache` | `myharborwavecache` |
| `other.person@example.test` | Unchanged |

Short identifiers that are not configured remain unchanged. **If you explicitly configure a short abbreviation, it also matches inside other words**, so avoid short terms likely to collide. Domains and email addresses have no separate allowlist, and the plugin does not automatically hide email local parts, phone numbers, or identity document numbers.

All-uppercase, all-lowercase, and initial-capital forms are restored with the corresponding capitalization. Other mixed-case forms are inferred by character position, without a guarantee of an exact round trip. For case-sensitive paths or accounts, configure and verify `casePairs`.

<a id="化名选择与校验"></a>

## Choosing and validating aliases

Aliases are reserved terms. When an alias appears in tool arguments, the plugin cannot tell whether it refers to the original or to an actual account, domain, or file that happens to have the same name. Choose aliases that are not used in your working environment and verify round trips with fictional data. The [behavior guide](behavior.md#路径域名与账号) explains the path exception.

Do not choose mapping values that change shell semantics. The plugin does not automatically escape spaces, quotes, dollar signs, or other shell special characters after replacement, nor does it validate whether an alias is suitable for a particular account or domain format.

Configuration parsing rejects the following:

- Unknown fields, invalid JSON, blank terms, or an original and alias that are identical when case is ignored.
- Duplicate or substring conflicts among originals, among aliases, or between originals and aliases across mappings.
- Duplicate `casePairs` or variants that do not belong to their mapping; mappings containing the reserved marker `<PII_`.
- More than 262144 JavaScript code units, 256 mappings, 32 case-variant pairs per mapping, or 500 code units in a single term.

If validation fails, the entire configuration is disabled; entries are not loaded partially. The limits and validation are implemented in [configuration.js](../../plugins/my-privacy/lib/configuration.js) and [privacy.js](../../plugins/my-privacy/lib/privacy.js), respectively.

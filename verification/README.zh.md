# 验证插件修改

[English](README.md) | 中文

本页面向修改插件的开发者：先运行纯逻辑和 Mod 测试，再用隔离的 Claude Code 会话验证本地工具执行、文本替换和后续会话。安装与日常使用见[仓库首页](../README.zh.md)，实现说明见[开发架构](../docs/developer/architecture.zh.md)。

<a id="运行当前检查"></a>

## 运行当前检查

需要 Node.js（含 npm）、Python 3，以及支持 `plugin validate` 和 `plugin test` 的 Claude Code。原生工具与终端显示回归还要求 macOS 的 `/usr/bin/sandbox-exec`。这些检查已在 macOS、Claude Code **2.1.290** 上通过；其他版本和平台需要重新验证。

从仓库根目录进入插件目录，执行：

```sh
cd plugins/my-privacy
npm test
claude plugin validate --strict .
claude plugin test .
```

然后回到仓库根目录运行原生工具回归：

```sh
cd ../..
./verification/run.sh
```

[`run.sh`](run.sh) 调用 [`run-targeted.py`](run-targeted.py)。当前执行回归以此脚本为准，不需要运行本目录的历史探测脚本。

如需单独检查终端回复显示，可从仓库根目录运行可选的 [`run-display.py`](run-display.py) 检查：

```sh
python3 verification/run-display.py
```

| 检查 | 通过标准 |
| --- | --- |
| `npm test` | 纯替换、配置解析、内容处理、工具策略和审计测试全部通过。 |
| `claude plugin validate --strict .` | 插件清单与 Mod 声明校验通过。 |
| `claude plugin test .` | Mod 事件测试全部通过，包括仅用于显示的回复恢复、模型与会话文本保持不变、异常放行、原生错误保留与配置缺失场景。 |
| `./verification/run.sh` | 退出码为 `0`，输出的 `passed` 为 `true`，`checks` 内各项均为 `true`。 |
| `python3 verification/run-display.py` | 退出码为 `0`，输出的 `passed` 为 `true`，`interactive` 和 `print` 内各项均为 `true`。 |

原生工具回归有意执行失败命令、读取不存在的文件，并传入空、无效和不可用配置。这些是验证场景；是否通过以检查结果为准。缺少平台或 CLI 前提时，报告会标记 `prerequisitesMissing` 并以非零状态退出。

<a id="隔离方式与结果"></a>

## 隔离方式与结果

原生工具回归将插件复制到私有临时目录，使用独立的 `CLAUDE_CONFIG_DIR`，并为每个 Claude 子进程明确设置 `CLAUDE_MY_PRIVACY_CONFIG`。[`synthetic_config.py`](synthetic_config.py) 提供虚构人物与公司映射；脚本不复制个人映射、凭据、设置、历史会话或项目文件。

辅助 Mod 提供固定的模型响应，Claude Code 执行真实的 Bash、Read、Write 和 Edit 工具。`sandbox-exec` 禁止网络连接，测试使用无效 API key。原生权限跳过仅用于这个禁止联网的临时测试环境；不要在日常会话中启用辅助模型 Mod。

脚本检查配置词在命令和文件操作中的恢复、工具返回文本的替换、无关文本保持原样、原生失败的错误信息，以及继续或恢复会话时不重复执行工具。空、无效和不可用配置还需保持工具可用、无隐式映射，并报告正确配置状态。

结果仅包含派生的布尔值、计数和结构化状态，打印到终端并保存为 `verification/evidence/targeted-latest-summary.json`。该报告已被 Git 忽略。临时会话、子进程输出、映射和测试文件在运行结束时清理。

可选的显示检查使用临时插件、虚构映射、独立配置、无效 API key 和同样禁止联网的沙箱，不启用原生工具。它验证真实终端回复中的恢复文本、下一轮模型输入和已保存助手文本中的化名，以及无界面模式下原样保留的化名输出。只在 Git 忽略的 `verification/evidence/display-latest-summary.json` 中保留派生检查结果；临时终端输出和会话会被删除。

如果检查失败，先查看输出中的 `checks`、`timedOut`、`prerequisitesMissing` 和 `moduleLoadError` 等字段，区分断言失败、超时、环境缺失与加载失败。不要用旧报告替代本次运行结果。

<a id="验证边界"></a>

## 验证边界

这组检查验证 Mod 可见的消息和工具处理，不检查完整的网络请求正文，也不调用真实模型或远程服务。通过测试不能证明所有请求、日志或宿主元数据都已脱敏；固定工具历史等内容仍可能处于 Mod 的改写范围之外。具体限制见[替换行为与覆盖边界](../docs/user/behavior.zh.md)。

原生工具回归使用非交互式 CLI 输出，不能证明交互界面中的助手回复恢复。可选的显示检查覆盖真实终端中的固定虚构回复；普通 `--print` 输出保留化名。Mod 测试通过 `ui.render` 检查部分及完整文本块和模拟的客户端属性，但不能证明真实流式输出、复制或导出、其他客户端或跨块恢复的覆盖。

<a id="历史探测与归档证据"></a>

## 历史探测与归档证据

以下脚本保留先前调查方法。它们包含旧版拦截、通用 PII 占位符或 Shell 前缀策略的预期，可能在当前版本失败，**不属于当前验收检查**。这些脚本也使用显式的虚构映射配置，避免回退到个人映射。

| 脚本 | 历史用途 |
| --- | --- |
| [`run.py`](run.py) 与 [`mock-model/`](mock-model/) | 最初的文本、文件替换与保存或恢复会话时的拦截行为。 |
| [`run-tools.py`](run-tools.py) | 原生可选参数、Shell 前缀解析和权限拒绝；诊断模式只修改临时插件副本。 |
| [`run-symlinks.py`](run-symlinks.py) | 化名目录软链接、Shell 分隔符与文件工具；链接仅创建在临时目录中。 |
| [`run-errors-audit.py`](run-errors-audit.py) | 原生错误输出类型修复前后的差异，以及审计元数据持久化。 |
| [`run-recovery.py`](run-recovery.py) | 未完成且已被取代的恢复方案调查。现行策略没有隐私历史锁，`/my-privacy-recover` 仅提供说明。 |

[`evidence/`](evidence/) 中的归档 JSON 记录当时的观察与计数，用于追溯旧策略，不代表当前版本的验证结果。`mock-model/` 中的辅助插件也仅用于测试。

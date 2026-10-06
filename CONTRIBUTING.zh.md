# 贡献与验证

[English](CONTRIBUTING.md) | 中文

修改前阅读 [AGENTS.md](AGENTS.zh.md) 和受影响的行为文档。所有公开示例和测试使用虚构数据；真实映射、运行日志、账号配置和稳定版备份保留在仓库外。

<a id="开发环境"></a>

## 开发环境

纯 JavaScript 测试使用 Node.js 内置测试运行器，无需安装项目依赖。插件验证和 Mod 测试需要支持当前接口的 Claude Code；离线 CLI 回归还需要 macOS、Python 3 和 `sandbox-exec`。具体范围见[验证说明](verification/README.zh.md)。

从仓库根目录执行：

```sh
npm --prefix plugins/my-privacy test
claude plugin validate --strict .
claude plugin validate --strict plugins/my-privacy
claude plugin test plugins/my-privacy
```

涉及工具恢复、会话处理或配置加载时，再运行：

```sh
./verification/run.sh
```

只运行与修改相关的检查；不要把历史探针当成当前发布门槛。宿主生成的类型文件和当前验证报告已被 `.gitignore` 排除。

<a id="documentation"></a>

## 文档

文档按读者任务分层，写作及证据规则见 [docs/AGENTS.md](docs/AGENTS.zh.md)。先校正源码拥有的事实，再修改说明；不要把一次会话的推断写成已验证行为。

检查修改和新增文档的链接、锚点、代码块及空白，再运行 `git diff --check`。该命令不检查未跟踪文件，应单独检查新增文件，不能将空输出当作全部文档已通过。

使用 `python3 scripts/check-translations.py` 检查全部配对。确认一组文档语义一致后，用 `python3 scripts/check-translations.py --write <pair>` 记录该组；只有明确要记录全部已评审配对时才使用 `--write --all`。配对规则见[双语文档说明](docs/i18n/README.zh.md)。

<a id="提交和发布前"></a>

## 提交和发布前

检查拟提交文件以及已有 Git 历史，确认没有真实姓名、公司标识、词表、凭据或本机路径。忽略规则只能防止部分文件被新增，不能清洗已进入历史的内容。

涉及版本更新时，同步插件清单、marketplace 条目、`package.json` 和审计版本常量；更新受影响文档并报告实际运行的检查。插件默认词表应始终为空。

本项目当前为 `UNLICENSED`。公开发布前需由维护者选择项目许可证。准备文档或连接 GitHub 本身不执行创建远程仓库、推送或发布。

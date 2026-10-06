# 仓库维护指南

[English](AGENTS.md) | 中文

MyPrivacy 是一个 Claude Code 插件，用于按配置替换姓名和公司名称。安装配置请阅读 [README.md](README.zh.md)；修改过滤行为前，请阅读 [docs/user/behavior.md](docs/user/behavior.zh.md)。

<a id="ownership-and-privacy"></a>

## 职责与隐私

- 生产代码位于 `plugins/my-privacy/`；`verification/` 负责离线 CLI（命令行界面）fixture（测试前置数据）和历史证据。
- 个人映射保存在仓库之外。禁止将真实姓名、公司标识、凭据、本地 transcript（文本记录）、设置或私有备份复制到源码、示例、测试、文档或提交中。请使用[虚构 fixture](examples/mappings.example.json)。
- 保持尽力替换、原生工具权限和每次工具调用只尝试执行一次的行为。文档工作不授权更改这些行为。
- 源码、已安装插件的缓存、外部配置和审计存储彼此独立。不得仅为验证文档而更新用户的运行时或运行 `install.py`。

<a id="documentation"></a>

## 文档

修改文档时，阅读 [docs/AGENTS.md](docs/AGENTS.zh.md)，了解文档职责、写作规则和证据要求。修改应限于请求涉及的范围。

项目文档按英文 `.md` 和简体中文 `.zh.md` 配对维护。任一语言均可作为更新的原文；同步更新对侧文件，并一并确认配对一致性。记录配对前，阅读 [docs/i18n/README.md](docs/i18n/README.zh.md) 中的双语审查和 Python 检查流程。

<a id="checks"></a>

## 检查

在仓库根目录执行：

```sh
npm --prefix plugins/my-privacy test
claude plugin validate --strict .
claude plugin validate --strict plugins/my-privacy
claude plugin test plugins/my-privacy
git diff --check
```

运行时行为或文档中的行为保证发生变化时，使用 `./verification/run.sh` 执行隔离的 macOS CLI 回归验证。前置条件和限制见 [verification/README.md](verification/README.zh.md)。历史运行器不作为当前验收门禁。只报告实际运行的检查；没有新理由时，不重复已通过的检查。

仓库存在未跟踪文件时，`git diff --check` 不会检查其内容。应将这些文件纳入人工 Markdown、链接和空白检查，不得仅为验证而暂存文件。

文档变更应运行 `python3 scripts/check-translations.py`。修改该检查器时，还应运行 `python3 -m unittest discover -s scripts/tests -p 'test_*.py'`。只有在对照两种语言核实含义后，才能用 `python3 scripts/check-translations.py --write <pair>` 记录已确认的翻译。

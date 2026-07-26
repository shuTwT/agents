# Feishu Agents

一个面向飞书开放平台开发者的 Agent 插件市场。

本项目不复制飞书官方文档，而是提供可复用的开发工作流、TypeScript/Node.js 模板、权限与事件检查清单，以及 API 集成代码生成流程。遇到 API 契约、权限或事件字段不确定时，优先使用[飞书官方文档检索 MCP](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/mcp_integration/install-and-use-document-search-mcp)。

## 当前插件

`feishu-open-platform` 是首个插件，当前包含：

- `feishu-api-developer`：负责把业务需求转成可验证的飞书 API 集成方案。
- `feishu-api-integration`：提供 API 定位、权限确认、TypeScript 客户端、错误处理和测试的工作流。
- `api-integration`：以命令方式启动完整 API 集成流程。

## 仓库结构

```text
.
├── .claude-plugin/marketplace.json      # Claude Code 市场源
├── .agents/plugins/marketplace.json     # 已提交的 Codex 市场清单
├── .cursor-plugin/                      # 已提交的 Cursor Registry/Manifest
├── gemini-extension.json                # 已提交的 Gemini 轻量 Manifest
├── plugins/feishu-open-platform/        # 唯一插件源码
├── docs/                                # 自动生成的插件、Agent、Skill、Command、Harness 目录
└── tools/                               # Adapter、生成器、校验器及 tools/tests
```

运行 `make generate-all` 后，还会在本地生成 `.codex/`、`.opencode/`、`.copilot/` 以及 Gemini 的 `agents/`、`skills/`、`commands/`。这些转换树体积会随插件数量增长，因此由 Git 忽略，不进入提交。

## 本地检查

```bash
make generate-all
make check-drift
make garden STRICT=1
make validate
make test
make release-check
```

生成器同时兼容上游调用风格：

```bash
make generate HARNESS=codex
make generate HARNESS=gemini PLUGIN=feishu-open-platform
python3 tools/generate.py --harness opencode --all --prune --strict
python3 tools/generate.py --harness cursor --all --output-root /tmp/agents-output
```

生成后可按上游方式安装或卸载本地 OpenCode/Copilot symlink：

```bash
make install-opencode
make uninstall-opencode
make install-copilot
make uninstall-copilot
```

`plugins/` 和 `.claude-plugin/marketplace.json` 是唯一源码。Git 只提交 `.agents/plugins/marketplace.json`、插件内 `.codex-plugin/plugin.json`、`.cursor-plugin/`、`gemini-extension.json` 和 `docs/` 等轻量生成物；其他 Harness 转换树在 clone 后按需生成。CI 会检查轻量生成物漂移，并重新生成全部运行时产物进行结构校验和测试。

版本采用手动 SemVer 和 `CHANGELOG.md`。当前支持 Claude Code、Codex、OpenCode、Cursor、Gemini CLI 和 GitHub Copilot；不安装或调用真实 CLI，不内置飞书 MCP 配置，也不读取或保存飞书凭证。

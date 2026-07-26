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
├── .agents/plugins/marketplace.json     # Codex 市场清单
├── plugins/feishu-open-platform/        # 唯一插件源码
├── docs/                                # 自动生成的插件、Agent、Skill、Command 目录
├── tools/                               # 生成器和校验器
└── tests/                               # 市场与生成器测试
```

## 本地检查

```bash
make generate-all
make check-drift
make validate
make test
make release-check
```

`plugins/` 和 `.claude-plugin/marketplace.json` 是唯一源码；`.codex/`、`.opencode/`、`opencode.json`、`.codex-plugin/` 以及 `docs/` 都由生成器维护。CI 会在生成后检查提交内容是否发生漂移。

版本采用手动 SemVer 和 `CHANGELOG.md`。当前阶段只支持 Codex、Claude Code 和 OpenCode；不内置飞书 MCP 配置，也不读取或保存飞书凭证。

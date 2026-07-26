# Feishu Agents

> 面向飞书开放平台开发的 Agent 插件市场：目前包含 **1 个插件、1 个 Agent、1 个 Skill、1 个 Command**。
>
> 使用一套 Claude Code Markdown 源码，同时适配 OpenAI Codex CLI、Cursor、OpenCode、Gemini CLI 和 GitHub Copilot。

[![Claude Code](https://img.shields.io/badge/Claude%20Code-native-blueviolet)](#claude-code)
[![Codex CLI](https://img.shields.io/badge/Codex%20CLI-supported-black)](docs/harnesses.md)
[![Cursor](https://img.shields.io/badge/Cursor-supported-purple)](docs/harnesses.md)
[![OpenCode](https://img.shields.io/badge/OpenCode-supported-green)](docs/harnesses.md)
[![Gemini CLI](https://img.shields.io/badge/Gemini%20CLI-supported-blue)](docs/harnesses.md)
[![GitHub Copilot](https://img.shields.io/badge/Copilot-supported-lightgrey)](docs/harnesses.md)

> [!NOTE]
> `plugins/` 是唯一内容源码。每个目标 Harness 都获得符合自身格式的 Agent、Skill 和 Command，而不是维护五套彼此独立的插件副本。完整能力与降级规则见 [Harness 能力矩阵](docs/harnesses.md)。

## 快速开始

选择你正在使用的 Harness。

### Claude Code

```text
/plugin marketplace add shuTwT/agents
/plugin install feishu-open-platform
```

Claude Code 直接读取 `.claude-plugin/marketplace.json` 和 `plugins/feishu-open-platform/`。

### OpenAI Codex CLI

仓库提交了轻量 Codex Registry 和插件 Manifest，可直接从源码安装：

```bash
npx codex-marketplace add shuTwT/agents
```

本地开发时也可以生成 Codex Agent 和 Skill：

```bash
gh repo clone shuTwT/agents ~/feishu-agents
cd ~/feishu-agents
make generate HARNESS=codex
```

### Cursor

在 Cursor 中添加 `shuTwT/agents` Marketplace，然后安装：

```text
/plugin install feishu-open-platform
```

Cursor 使用已提交的 `.cursor-plugin/` Registry，并直接复用插件源码，不复制组件树。

### OpenCode

```bash
gh repo clone shuTwT/agents ~/feishu-agents
cd ~/feishu-agents
make install-opencode
```

卸载仓库创建的 symlink：

```bash
make uninstall-opencode
```

### Gemini CLI

```bash
gh repo clone shuTwT/agents ~/feishu-agents
cd ~/feishu-agents
make generate HARNESS=gemini
gemini extensions install .
```

Gemini 使用根目录 `gemini-extension.json`，并在本地生成 `agents/`、`skills/` 和 TOML `commands/`。

### GitHub Copilot

```bash
gh repo clone shuTwT/agents ~/feishu-agents
cd ~/feishu-agents
make install-copilot
```

卸载仓库创建的 symlink：

```bash
make uninstall-copilot
```

## 包含内容

| 类型 | 数量 | 说明 |
|---|---:|---|
| **Plugins** | 1 | 可独立安装的飞书开放平台开发插件 |
| **Agents** | 1 | 将业务需求转成可验证 API 集成方案的领域 Agent |
| **Skills** | 1 | API 定位、权限与 token 核对、实现和测试工作流 |
| **Commands** | 1 | 启动完整 API 集成流程的用户命令 |
| **Harness adapters** | 5 | Codex、Cursor、OpenCode、Gemini CLI、Copilot |

浏览自动生成的目录：

[插件](docs/plugins.md) · [Agents](docs/agents.md) · [Skills](docs/skills.md) · [Commands](docs/commands.md)

## 当前插件

### `feishu-open-platform`

面向 TypeScript/Node.js 项目的飞书开放平台 API 集成工作流。

| 组件 | 名称 | 用途 |
|---|---|---|
| Agent | `feishu-api-developer` | 分析业务目标，确认 API、权限、token、字段和限制，给出可验证的实施方案 |
| Skill | `feishu-api-integration` | 组织 API 契约核对、客户端设计、错误处理、测试和上线检查 |
| Command | `api-integration` | 以命令方式启动完整 API 集成流程 |

这个插件不会复制或猜测飞书官方接口契约。当 API、权限、事件字段或 token 规则不确定时，应优先查询[飞书开放平台官方文档](https://open.feishu.cn/document/)或使用[官方文档检索 MCP](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/mcp_integration/install-and-use-document-search-mcp)。

## 工作原理

每个插件都是隔离、可组合的目录单元。安装一个插件只加载该插件的组件，而不是把整个 Marketplace 注入上下文。

```text
plugins/feishu-open-platform/
├── .claude-plugin/
│   └── plugin.json
├── .codex-plugin/
│   └── plugin.json
├── agents/
│   └── feishu-api-developer.md
├── commands/
│   └── api-integration.md
└── skills/
    └── feishu-api-integration/
        ├── SKILL.md
        └── references/
            └── api-contract-checklist.md
```

生成链路：

```text
plugins/ + .claude-plugin/marketplace.json
                    │
                    ▼
     PluginSource / AgentSource / SkillSource / CommandSource
                    │
                    ▼
       capability matrix + harness adapters
                    │
        ┌───────────┼───────────┬───────────┬───────────┐
        ▼           ▼           ▼           ▼           ▼
      Codex      OpenCode     Cursor      Gemini      Copilot
```

Adapter 负责处理：

- Harness 原生文件格式。
- Claude 工具名到目标工具名或动作描述的转换。
- `opus`、`sonnet`、`haiku`、`inherit` 模型别名映射。
- 不支持字段的显式 warning。
- Command 到 Skill/TOML 等目标语义的转换。
- 组件 namespace、字节上限和权限格式。

## 多 Harness 支持

| Harness | 生成或读取内容 | 说明 |
|---|---|---|
| **Claude Code** | `.claude-plugin/marketplace.json`、`plugins/` | 源码事实来源 |
| **Codex CLI** | `.agents/plugins/marketplace.json`、`plugins/*/.codex-plugin/plugin.json`；本地 `.codex/agents/`、`.codex/skills/` | Command 转 Skill；检查 8 KB Skill 上限 |
| **Cursor** | `.cursor-plugin/` | 薄 Registry，直接指向插件源码 |
| **OpenCode** | `.opencode/agents/`、`.opencode/skills/`、`.opencode/commands/`、`opencode.json` | Agent 工具限制转换为 `permission` block |
| **Gemini CLI** | `gemini-extension.json`、`agents/`、`skills/`、`commands/*.toml` | 大 Command 使用 `@{plugins/...}` 注入源码 |
| **GitHub Copilot** | `.copilot/agents/`、`.copilot/skills/`、`.copilot/commands/` | Command 转为可手动调用的 Skill |

完整差异见 [docs/harnesses.md](docs/harnesses.md)。

## 生成物策略

仓库只提交安装和审查所需的轻量生成物：

```text
.agents/plugins/marketplace.json
.cursor-plugin/
gemini-extension.json
plugins/*/.codex-plugin/plugin.json
docs/
```

以下转换树由本地生成并被 Git 忽略：

```text
.codex/
.opencode/
opencode.json
.copilot/
agents/
skills/
commands/
```

这种方式保持 `plugins/` 为唯一内容源码，同时避免插件数量增长后把同一内容复制到多个 Harness 并提交。

## 开发与质量检查

只需要 Python 标准库，不需要模型密钥或生产依赖。

```bash
make generate-all          # 生成五个目标 Harness
make check-drift           # 检查已提交 Registry、Manifest 和目录文档
make garden STRICT=1       # 检查漂移、死链、上下文和 Skill 上限
make validate              # 生成并执行严格结构校验
make test                  # 运行 tools/tests 下的静态回归测试
make release-check         # 校验 SemVer、CHANGELOG 和轻量生成物
```

也可以使用与上游兼容的生成接口：

```bash
make generate HARNESS=codex
make generate HARNESS=gemini PLUGIN=feishu-open-platform

python3 tools/generate.py --harness opencode --all --prune
python3 tools/generate.py --harness cursor --all --output-root /tmp/agents-output
python3 tools/generate.py --harness all --check
```

当前质量基线包括：

- Marketplace、Manifest、Frontmatter 和 SemVer 校验。
- 五个 Adapter 的 JSON、TOML 和 Markdown 静态解析。
- 多插件生成、删除、重命名和路径冲突回归。
- 工具名、模型映射和 Command 降级测试。
- 轻量生成物逐字节漂移检查。
- 安装器 symlink 冲突与卸载往返测试。
- 凭证特征扫描。

当前阶段不运行真实 Harness CLI，也不调用 LLM Judge、Elo 或 Monte Carlo。

## 添加插件

1. 在 `plugins/<name>/` 添加 `.claude-plugin/plugin.json`。
2. 按需添加 `agents/`、`skills/` 和 `commands/`。
3. 在 `.claude-plugin/marketplace.json` 增加本地 source entry。
4. 更新版本和 `CHANGELOG.md`。
5. 运行：

```bash
make generate-all
make check-drift
make garden STRICT=1
make validate
make test
```

生成器会自动更新 Codex/Cursor Registry、Gemini Manifest、Harness 运行时产物和目录文档。

## 文档

- [docs/plugins.md](docs/plugins.md)：插件目录
- [docs/agents.md](docs/agents.md)：Agent 目录
- [docs/skills.md](docs/skills.md)：Skill 目录
- [docs/commands.md](docs/commands.md)：Command 目录
- [docs/harnesses.md](docs/harnesses.md)：能力矩阵、输出路径和降级规则
- [CHANGELOG.md](CHANGELOG.md)：版本变更记录

## 安全边界

- 不在仓库中存放飞书 App Secret、access token、用户数据或客户数据。
- 不编造飞书 API、权限、事件 payload 或 token 规则。
- 生成代码前先核对官方文档和 API 契约。
- `.env` 示例只能包含变量名和占位符，不能包含真实值。
- 安装器只管理由本仓库生成的 symlink，不覆盖普通文件。

## License

MIT，见 [LICENSE](LICENSE)。

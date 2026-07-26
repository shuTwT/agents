# Harness 能力矩阵

> 本文件由 `tools/adapters/capabilities.py` 生成，请修改能力矩阵源码。

| Harness | Skills | Agents | Commands | Marketplace | 工具格式 | 上下文文件 | 生成路径 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `claude-code` | yes | yes | yes | yes | CamelCase | CLAUDE.md | `plugins/; .claude-plugin/` |
| `codex` | yes | yes | no | no | none | AGENTS.md | `.agents/; .codex/; plugins/*/.codex-plugin/` |
| `opencode` | yes | yes | yes | no | lowercase | AGENTS.md | `.opencode/; opencode.json` |
| `cursor` | yes | yes | yes | yes | lowercase | AGENTS.md | `.cursor-plugin/` |
| `gemini` | yes | yes | yes | no | lowercase | AGENTS.md | `gemini-extension.json; agents/; skills/; commands/` |
| `copilot` | yes | yes | no | no | lowercase | AGENTS.md | `.copilot/` |

## 详细能力

| Harness | 并行 Agent | 工具白名单 | Todo | Task/Agent | MCP | Hooks | 上下文上限 | Skill 上限 | 裸模型别名 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `claude-code` | yes | yes | yes | yes | yes | yes | 150 lines | none | yes | 源码事实来源。 |
| `codex` | yes | no | no | no | yes | no | 150 lines | 8192 bytes | no | Command 映射为 Skill。 |
| `opencode` | yes | yes | yes | yes | yes | yes | 150 lines | none | no | 使用 permission block。 |
| `cursor` | yes | no | no | yes | yes | no | 150 lines | none | no | Marketplace 指向插件源码，组件复用 source。 |
| `gemini` | yes | yes | no | yes | yes | no | 150 lines | none | no | 命令输出为 TOML。 |
| `copilot` | no | yes | no | yes | yes | no | 150 lines | none | no | Command 映射为可手动调用 Skill。 |

## 降级规则

- Codex Command 转换为 Skill，并将工具限制降级为 workspace sandbox。
- Gemini Command 转换为 TOML；协议较大时使用 `@{plugins/...}` 注入源码文件。
- Copilot Command 转换为 `user-invocable` Skill，同时保留 command 文件。
- Cursor 使用 marketplace/manifest 指向插件源码，不重复复制组件。
- 未被目标 harness 支持的 frontmatter 字段会在生成日志中输出 warning。

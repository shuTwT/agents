"""Generated marketplace and cross-harness documentation."""

from __future__ import annotations

from pathlib import Path

from .adapters.base import load_plugins, parse_frontmatter, read_json
from .adapters.capabilities import CAPABILITIES, supported_harnesses

DOC_FILES = (
    "docs/plugins.md",
    "docs/agents.md",
    "docs/skills.md",
    "docs/commands.md",
    "docs/harnesses.md",
)


def _cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def _source_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _harness_doc() -> str:
    lines = [
        "# Harness 能力矩阵",
        "",
        "> 本文件由 `tools/adapters/capabilities.py` 生成，请修改能力矩阵源码。",
        "",
        "| Harness | Skills | Agents | Commands | Marketplace | 工具格式 | 上下文文件 | 生成路径 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for harness_id in ["claude-code", *supported_harnesses()]:
        capability = CAPABILITIES[harness_id]
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    f"`{harness_id}`",
                    "yes" if capability.skills_native else "no",
                    "yes" if capability.agents_native else "no",
                    "yes" if capability.commands_native else "no",
                    "yes" if capability.plugin_marketplace else "no",
                    capability.tool_name_case,
                    capability.context_file_name or "none",
                    f"`{capability.generated_paths}`",
                )
            )
            + " |"
        )
    lines.extend([
        "",
        "## 详细能力",
        "",
        "| Harness | 并行 Agent | 工具白名单 | Todo | Task/Agent | MCP | Hooks | 上下文上限 | Skill 上限 | 裸模型别名 | 备注 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for harness_id in ["claude-code", *supported_harnesses()]:
        capability = CAPABILITIES[harness_id]
        lines.append(
            "| " + " | ".join(_cell(value) for value in (
                f"`{harness_id}`",
                "yes" if capability.parallel_agents else "no",
                "yes" if capability.tool_allowlist_per_agent else "no",
                "yes" if capability.todowrite else "no",
                "yes" if capability.task_spawn else "no",
                "yes" if capability.mcp_servers else "no",
                "yes" if capability.hooks else "no",
                f"{capability.context_file_max_lines} lines",
                "none" if capability.skill_body_max_bytes == 0 else f"{capability.skill_body_max_bytes} bytes",
                "yes" if capability.bare_model_aliases else "no",
                capability.notes,
            )) + " |"
        )
    lines.extend([
        "",
        "## 发布与跟踪策略",
        "",
        "- Git 只提交 Codex Registry、插件内 Codex Manifest、Cursor Registry/Manifest、`gemini-extension.json` 和本目录文档。",
        "- `.codex/`、`.opencode/`、`.copilot/` 以及 Gemini 的 `agents/`、`skills/`、`commands/` 是本地运行时生成物，默认由 Git 忽略。",
        "- 使用 `make generate-all` 重建运行时产物；使用 `make check-drift` 检查应提交的轻量生成物。",
        "",
        "## 降级规则",
        "",
        "- Codex Command 转换为 Skill，并将工具限制降级为 workspace sandbox。",
        "- Gemini Command 转换为 TOML；协议较大时使用 `@{plugins/...}` 注入源码文件。",
        "- Copilot Command 转换为 `user-invocable` Skill，同时保留 command 文件。",
        "- Cursor 使用 marketplace/manifest 指向插件源码，不重复复制组件。",
        "- 未被目标 harness 支持的 frontmatter 字段会在生成日志中输出 warning。",
        "",
    ])
    return "\n".join(lines)


def render_docs(root: Path) -> dict[str, str]:
    marketplace = read_json(root / ".claude-plugin/marketplace.json")
    plugins = load_plugins(root)
    entries = {entry.get("name"): entry for entry in marketplace.get("plugins", [])}

    plugin_lines = [
        "# 插件目录", "", "> 本文件由 `tools/generate.py` 生成，请修改 `plugins/` 和 marketplace 源文件。", "",
        "| 插件 | 版本 | 类别 | 描述 | 能力 |", "| --- | --- | --- | --- | --- |",
    ]
    agent_lines = ["# Agent 目录", "", "> 本文件由 `tools/generate.py` 生成。", "", "| 名称 | 插件 | 模型 | 描述 | 源文件 |", "| --- | --- | --- | --- | --- |"]
    skill_lines = ["# Skill 目录", "", "> 本文件由 `tools/generate.py` 生成。", "", "| 名称 | 插件 | 描述 | references | assets | 源文件 |", "| --- | --- | --- | --- | --- | --- |"]
    command_lines = ["# Command 目录", "", "> 本文件由 `tools/generate.py` 生成。", "", "| 名称 | 插件 | 描述 | 参数提示 | 源文件 |", "| --- | --- | --- | --- | --- |"]

    for plugin in plugins:
        entry = entries.get(plugin.name, {})
        capabilities = ", ".join(plugin.interface.get("capabilities", []))
        plugin_lines.append(
            "| " + " | ".join(_cell(value) for value in (
                f"`{plugin.name}`", plugin.version,
                entry.get("category", plugin.interface.get("category", "")),
                plugin.description, capabilities,
            )) + " |"
        )
        for agent in plugin.agents:
            agent_lines.append(
                "| " + " | ".join(_cell(value) for value in (
                    f"`{plugin.name}__{agent.name}`", f"`{plugin.name}`", agent.model,
                    agent.description, f"`{_source_path(root, agent.path)}`",
                )) + " |"
            )
        for skill in plugin.skills:
            skill_lines.append(
                "| " + " | ".join(_cell(value) for value in (
                    f"`{plugin.name}__{skill.name}`", f"`{plugin.name}`", skill.description,
                    "yes" if skill.references_dir else "no", "yes" if skill.assets_dir else "no",
                    f"`{_source_path(root, skill.path)}`",
                )) + " |"
            )
        for command in plugin.commands:
            command_lines.append(
                "| " + " | ".join(_cell(value) for value in (
                    f"`{plugin.name}__{command.name}`", f"`{plugin.name}`", command.description,
                    command.argument_hint, f"`{_source_path(root, command.path)}`",
                )) + " |"
            )

    return {
        DOC_FILES[0]: "\n".join(plugin_lines) + "\n",
        DOC_FILES[1]: "\n".join(agent_lines) + "\n",
        DOC_FILES[2]: "\n".join(skill_lines) + "\n",
        DOC_FILES[3]: "\n".join(command_lines) + "\n",
        DOC_FILES[4]: _harness_doc(),
    }


def generate_docs(root: Path, *, source_root: Path | None = None) -> int:
    rendered = render_docs(source_root or root)
    for relative, content in rendered.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return len(rendered)

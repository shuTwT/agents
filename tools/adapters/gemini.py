"""Gemini CLI adapter."""

from __future__ import annotations

import json
from pathlib import Path

from .base import EmitResult, HarnessAdapter, PluginSource, render_frontmatter, resolve_agent_model, rewrite_tool_references
from .capabilities import TOOL_NAME_MAPS


INLINE_BODY_THRESHOLD = 4 * 1024


def _escape_toml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')


def _toml_command(description: str, prompt: str) -> str:
    return f'description = "{_escape_toml(description)}"\nprompt = """\n{_escape_toml(prompt)}\n"""\n'


def _gemini_frontmatter(fields: dict) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(str(item) for item in value)}]")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {str(value).replace(chr(10), ' ').strip()}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def _copy_support_files(skill, destination: Path, adapter: HarnessAdapter) -> None:
    for directory in (skill.references_dir, skill.assets_dir):
        if directory is None:
            continue
        for source in sorted(directory.rglob("*")):
            if source.is_file():
                adapter.mirror_file(source, destination / directory.name / source.relative_to(directory))


class GeminiAdapter(HarnessAdapter):
    harness_id = "gemini"
    clean_paths = ("gemini-extension.json", "agents", "skills", "commands")

    def emit_plugin(self, plugin: PluginSource) -> EmitResult:
        result = EmitResult()
        for skill in plugin.skills:
            skill_id = f"{plugin.name}__{skill.name}"
            content = _gemini_frontmatter({**skill.frontmatter, "name": skill_id})
            content += rewrite_tool_references(skill.body, self.harness_id)
            destination = Path("skills") / skill_id
            self.write(destination / "SKILL.md", content)
            _copy_support_files(skill, destination, self)

        for agent in plugin.agents:
            agent_id = f"{plugin.name}__{agent.name}"
            model = resolve_agent_model(agent, self.harness_id, result)
            for field in sorted(set(agent.frontmatter) - {"name", "description", "model", "tools", "allowed-tools"}):
                result.warnings.append(f"agent `{agent_id}`: Gemini dropped unsupported field `{field}`")
            fields = {"name": agent_id, "description": agent.description, "model": model}
            if agent.tools:
                fields["tools"] = [TOOL_NAME_MAPS["gemini"].get(tool, tool) for tool in agent.tools]
            content = _gemini_frontmatter(fields) + rewrite_tool_references(agent.body, self.harness_id)
            self.write(Path("agents") / f"{agent_id}.md", content)

        for command in plugin.commands:
            description = command.description or command.name.replace("-", " ").title()
            if len(command.body.encode("utf-8")) <= INLINE_BODY_THRESHOLD:
                prompt = self._inline_command(plugin, command)
            else:
                prompt = self._injected_command(plugin, command)
            self.write(Path("commands") / plugin.name / f"{command.name}.toml", _toml_command(description, prompt))

        return result

    def emit_global(self, plugins: list[PluginSource]) -> EmitResult:
        marketplace = json.loads((self.root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        metadata = marketplace.get("metadata", {})
        extension = {
            "name": marketplace.get("name", "agent-marketplace"),
            "version": metadata.get("version", "0.0.0"),
            "description": metadata.get("description", ""),
            "contextFileName": "AGENTS.md",
        }
        self.write_json("gemini-extension.json", extension)
        return EmitResult()

    def _inline_command(self, plugin: PluginSource, command) -> str:
        lines = [
            f"You are running the `{command.name}` command from the `{plugin.name}` plugin.",
            "",
            "## Protocol",
            "",
            rewrite_tool_references(command.body, self.harness_id).strip(),
            "",
        ]
        if command.argument_hint:
            lines.extend([f"Arguments: {command.argument_hint}", ""])
        lines.append("{{args}}")
        return "\n".join(lines)

    def _injected_command(self, plugin: PluginSource, command) -> str:
        lines = [
            f"You are running the `{command.name}` command from the `{plugin.name}` plugin.",
            "",
            "## Protocol",
            "",
            "Read the full protocol definition before executing.",
            "",
            f"@{{plugins/{plugin.name}/commands/{command.name}.md}}",
            "",
            "## Execution",
            "",
            "Execute the steps sequentially and pause at every checkpoint.",
            "",
        ]
        if command.argument_hint:
            lines.extend([f"Arguments: {command.argument_hint}", ""])
        lines.append("{{args}}")
        return "\n".join(lines)

    def write_json(self, relative: str | Path, value: dict) -> Path:
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return Path(relative)

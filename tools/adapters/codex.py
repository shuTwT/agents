"""Codex CLI adapter."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .base import (
    EmitResult,
    HarnessAdapter,
    PluginSource,
    SkillSource,
    load_plugins,
    render_frontmatter,
    resolve_agent_model,
    rewrite_tool_references,
)


def _copy_support_files(skill: SkillSource, destination: Path, adapter: HarnessAdapter) -> None:
    for directory in (skill.references_dir, skill.assets_dir):
        if directory is None:
            continue
        label = directory.name
        for source in sorted(directory.rglob("*")):
            if source.is_file():
                relative = source.relative_to(directory)
                adapter.mirror_file(source, destination / label / relative)


class CodexAdapter(HarnessAdapter):
    harness_id = "codex"
    clean_paths = (".codex", ".agents/plugins/marketplace.json")

    def clean(self) -> None:
        super().clean()
        plugins_root = self.root / "plugins"
        if plugins_root.is_dir():
            for path in plugins_root.glob("*/.codex-plugin/plugin.json"):
                path.unlink()

    def emit_plugin(self, plugin: PluginSource) -> EmitResult:
        result = EmitResult()
        output_root = self.root / ".codex"

        manifest = dict(plugin.plugin_json)
        manifest["skills"] = "./skills/"
        self.write_json(Path("plugins") / plugin.name / ".codex-plugin/plugin.json", manifest)

        for agent in plugin.agents:
            if agent.tools:
                result.warnings.append(f"agent `{plugin.name}__{agent.name}`: Codex does not support per-agent tool allowlists; dropped tools")
            dropped = sorted(set(agent.frontmatter) - {"name", "description", "model"})
            for field in dropped:
                if field not in {"tools", "allowed-tools"}:
                    result.warnings.append(f"agent `{plugin.name}__{agent.name}`: Codex dropped unsupported field `{field}`")
            model = resolve_agent_model(agent, self.harness_id, result)
            instructions = rewrite_tool_references(agent.body, self.harness_id)
            instructions = instructions.replace('"""', '\\"\\"\\"')
            content = (
                f"name = {json.dumps(f'{plugin.name}__{agent.name}')}\n"
                f"description = {json.dumps(agent.description, ensure_ascii=False)}\n"
                f"model = {json.dumps(model)}\n"
                'sandbox_mode = "workspace-write"\n'
                "developer_instructions = \"\"\"\n"
                f"{instructions}\n"
                "\"\"\"\n"
            )
            self.write(Path(".codex") / "agents" / f"{plugin.name}__{agent.name}.toml", content)

        for skill in plugin.skills:
            for field in sorted(set(skill.frontmatter) - {"name", "description"}):
                result.warnings.append(f"skill `{plugin.name}__{skill.name}`: Codex dropped unsupported field `{field}`")
            skill_name = f"{plugin.name}__{skill.name}"
            content = render_frontmatter({"name": skill_name, "description": skill.description})
            content += rewrite_tool_references(skill.body, self.harness_id)
            destination = Path(".codex") / "skills" / skill_name
            self.write(destination / "SKILL.md", content)
            _copy_support_files(skill, destination, self)

        for command in plugin.commands:
            for field in sorted(set(command.frontmatter) - {"description"}):
                result.warnings.append(f"command `{plugin.name}__{command.name}`: Codex dropped unsupported field `{field}`")
            skill_name = f"{plugin.name}__{command.name}__command"
            content = render_frontmatter({"name": skill_name, "description": command.description})
            content += rewrite_tool_references(command.body, self.harness_id)
            self.write(Path(".codex") / "skills" / skill_name / "SKILL.md", content)

        return result

    def emit_global(self, plugins: list[PluginSource]) -> EmitResult:
        marketplace = json.loads((self.root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        output = {
            "name": marketplace["name"],
            "metadata": marketplace.get("metadata", {}),
            "plugins": [],
        }
        for plugin in plugins:
            entry = plugin.marketplace_entry
            output["plugins"].append(
                {
                    "name": plugin.name,
                    "description": plugin.description,
                    "version": plugin.version,
                    "author": plugin.author,
                    "source": {"source": "local", "path": f"./plugins/{plugin.name}"},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": entry.get("category", plugin.interface.get("category", "Coding")),
                }
            )
        self.write_json(Path(".agents/plugins/marketplace.json"), output)
        return EmitResult()

    def write_json(self, relative: str | Path, value: dict) -> Path:
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return Path(relative)

"""OpenCode adapter."""

from __future__ import annotations

import json
from pathlib import Path

from .base import EmitResult, HarnessAdapter, PluginSource, SkillSource, render_frontmatter, resolve_agent_model, rewrite_tool_references


def _copy_support_files(skill: SkillSource, destination: Path, adapter: HarnessAdapter) -> None:
    for directory in (skill.references_dir, skill.assets_dir):
        if directory is None:
            continue
        label = directory.name
        for source in sorted(directory.rglob("*")):
            if source.is_file():
                adapter.mirror_file(source, destination / label / source.relative_to(directory))


class OpenCodeAdapter(HarnessAdapter):
    harness_id = "opencode"
    clean_paths = (".opencode", "opencode.json")

    def emit_plugin(self, plugin: PluginSource) -> EmitResult:
        before = len(self._written)
        result = EmitResult()
        for agent in plugin.agents:
            model = resolve_agent_model(agent, self.harness_id, result)
            for field in sorted(set(agent.frontmatter) - {"name", "description", "model", "tools", "allowed-tools"}):
                result.warnings.append(f"agent `{plugin.name}__{agent.name}`: OpenCode dropped unsupported field `{field}`")
            fields = {
                "description": agent.description,
                "mode": "subagent",
                "model": model,
            }
            if agent.tools:
                result.warnings.append(f"agent `{plugin.name}__{agent.name}`: OpenCode tool allowlist is normalized to the shared allow permission block")
            content = render_frontmatter(fields, include_permission=True)
            content += rewrite_tool_references(agent.body, self.harness_id)
            self.write(Path(".opencode") / "agents" / f"{plugin.name}__{agent.name}.md", content)

        for skill in plugin.skills:
            for field in sorted(set(skill.frontmatter) - {"name", "description"}):
                result.warnings.append(f"skill `{plugin.name}-{skill.name}`: OpenCode dropped unsupported field `{field}`")
            name = f"{plugin.name}-{skill.name}"
            content = render_frontmatter({"name": name, "description": skill.description})
            content += rewrite_tool_references(skill.body, self.harness_id)
            destination = Path(".opencode") / "skills" / name
            self.write(destination / "SKILL.md", content)
            _copy_support_files(skill, destination, self)

        for command in plugin.commands:
            for field in sorted(set(command.frontmatter) - {"description", "argument-hint"}):
                result.warnings.append(f"command `{plugin.name}__{command.name}`: OpenCode dropped unsupported field `{field}`")
            fields = {"description": command.description, "argument-hint": command.argument_hint}
            content = render_frontmatter(fields)
            content += rewrite_tool_references(command.body, self.harness_id)
            self.write(Path(".opencode") / "commands" / f"{plugin.name}__{command.name}.md", content)
        result.written.extend(self._written[before:])
        return result

    def emit_global(self, plugins: list[PluginSource]) -> EmitResult:
        path = self.write("opencode.json", json.dumps({"$schema": "https://opencode.ai/config.json"}, indent=2))
        return EmitResult(written=[path])

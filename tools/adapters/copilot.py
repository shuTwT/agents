"""GitHub Copilot adapter."""

from __future__ import annotations

from pathlib import Path

from .base import EmitResult, HarnessAdapter, PluginSource, SkillSource, render_frontmatter, resolve_agent_model, rewrite_tool_references
from .capabilities import TOOL_NAME_MAPS


def _copy_support_files(skill: SkillSource, destination: Path, adapter: HarnessAdapter) -> None:
    for directory in (skill.references_dir, skill.assets_dir):
        if directory is None:
            continue
        for source in sorted(directory.rglob("*")):
            if source.is_file():
                adapter.mirror_file(source, destination / directory.name / source.relative_to(directory))


class CopilotAdapter(HarnessAdapter):
    harness_id = "copilot"
    clean_paths = (".copilot",)

    def emit_plugin(self, plugin: PluginSource) -> EmitResult:
        result = EmitResult()
        for agent in plugin.agents:
            for field in sorted(set(agent.frontmatter) - {"name", "description", "model", "tools", "allowed-tools"}):
                result.warnings.append(f"agent `{plugin.name}__{agent.name}`: Copilot dropped unsupported field `{field}`")
            fields = {
                "name": f"{plugin.name}__{agent.name}",
                "description": agent.description or f"{agent.name} from {plugin.name}",
                "model": resolve_agent_model(agent, self.harness_id, result),
            }
            if agent.tools:
                fields["tools"] = [TOOL_NAME_MAPS["copilot"].get(tool, tool) for tool in agent.tools]
            content = render_frontmatter(fields) + rewrite_tool_references(agent.body, self.harness_id)
            self.write(Path(".copilot/agents") / f"{plugin.name}__{agent.name}.agent.md", content)

        for skill in plugin.skills:
            for field in sorted(set(skill.frontmatter) - {"name", "description", "allowed-tools", "user-invocable", "disable-model-invocation"}):
                result.warnings.append(f"skill `{plugin.name}__{skill.name}`: Copilot dropped unsupported field `{field}`")
            skill_id = f"{plugin.name}__{skill.name}"
            content = render_frontmatter({**skill.frontmatter, "name": skill_id})
            content += rewrite_tool_references(skill.body, self.harness_id)
            destination = Path(".copilot/skills") / skill_id
            self.write(destination / "SKILL.md", content)
            _copy_support_files(skill, destination, self)

        for command in plugin.commands:
            skill_id = f"{plugin.name}-{command.name}"
            fields = {
                "name": skill_id,
                "description": command.description or command.name.replace("-", " ").title(),
                "user-invocable": True,
                "disable-model-invocation": True,
            }
            if command.argument_hint:
                fields["argument-hint"] = command.argument_hint
            content = render_frontmatter(fields) + rewrite_tool_references(command.body, self.harness_id)
            self.write(Path(".copilot/skills") / skill_id / "SKILL.md", content)

            command_fields = {"description": command.description or command.name.replace("-", " ").title()}
            self.write(
                Path(".copilot/commands") / plugin.name / f"{command.name}.md",
                render_frontmatter(command_fields) + rewrite_tool_references(command.body, self.harness_id),
            )

        index_lines = [
            f"{plugin.description or plugin.name}.",
            "",
            f"This is the entry point for the `{plugin.name}` plugin.",
        ]
        if plugin.agents:
            index_lines.extend(["", "Agents: " + ", ".join(f"`{plugin.name}__{a.name}`" for a in plugin.agents) + "."])
        if plugin.skills:
            index_lines.extend(["", "Skills: " + ", ".join(f"`{plugin.name}__{s.name}`" for s in plugin.skills) + "."])
        if plugin.commands:
            index_lines.extend(["", "Commands: " + ", ".join(f"`/{plugin.name}:{c.name}`" for c in plugin.commands) + "."])
        index_lines.extend(["", "{{args}}"])
        self.write(Path(".copilot/commands") / plugin.name / "index.md", render_frontmatter({"description": plugin.description}) + "\n".join(index_lines))
        return result

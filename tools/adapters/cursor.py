"""Cursor marketplace adapter.

Cursor can consume the source plugin component tree directly, so this adapter
emits thin manifests rather than duplicating every agent and skill.
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import EmitResult, HarnessAdapter, PluginSource


def _author(author: dict) -> dict:
    if not isinstance(author, dict):
        return {}
    result = {"name": author.get("name", "")}
    if author.get("url"):
        result["url"] = author["url"]
    return {key: value for key, value in result.items() if value}


class CursorAdapter(HarnessAdapter):
    harness_id = "cursor"
    clean_paths = (".cursor-plugin",)

    def emit_plugin(self, plugin: PluginSource) -> EmitResult:
        manifest = {
            "name": plugin.name,
            "displayName": plugin.interface.get("displayName", plugin.name.replace("-", " ").title()),
            "version": plugin.version,
            "description": plugin.description,
            "author": _author(plugin.author),
        }
        for optional in ("homepage", "license"):
            if plugin.plugin_json.get(optional):
                manifest[optional] = plugin.plugin_json[optional]
        return EmitResult(written=[self.write_json(Path(".cursor-plugin/plugins") / f"{plugin.name}.json", manifest)])

    def emit_global(self, plugins: list[PluginSource]) -> EmitResult:
        marketplace = json.loads((self.source_root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        entries = []
        for plugin in plugins:
            entry = {
                "name": plugin.name,
                "source": f"./plugins/{plugin.name}",
                "version": plugin.version,
                "description": plugin.description,
                "author": _author(plugin.author),
            }
            for optional in ("homepage", "license", "category"):
                value = plugin.marketplace_entry.get(optional, plugin.plugin_json.get(optional))
                if value:
                    entry[optional] = value
            entries.append(entry)
        root_manifest = {
            "name": marketplace.get("name", "agent-marketplace"),
            "owner": marketplace.get("owner", {}),
            "metadata": marketplace.get("metadata", {}),
            "plugins": entries,
        }
        result = EmitResult(written=[self.write_json(Path(".cursor-plugin/marketplace.json"), root_manifest)])
        if plugins:
            bundle = {
                "name": root_manifest["name"],
                "displayName": root_manifest["name"].replace("-", " ").title(),
                "version": root_manifest["metadata"].get("version", "0.0.0"),
                "description": root_manifest["metadata"].get("description", ""),
                "author": _author(marketplace.get("owner", {})),
                "license": "MIT",
            }
            result.written.append(self.write_json(Path(".cursor-plugin/plugin.json"), bundle))
        return result

    def write_json(self, relative: str | Path, value: dict) -> Path:
        return self.write(relative, json.dumps(value, ensure_ascii=False, indent=2))

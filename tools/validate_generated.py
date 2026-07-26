#!/usr/bin/env python3
"""Validate source plugins and generated multi-harness artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from .adapters.capabilities import CAPABILITIES, supported_harnesses
    from .generate import ADAPTERS, DOC_FILES, ROOT, parse_frontmatter, render_docs
except ImportError:  # pragma: no cover - supports direct script execution.
    from adapters.capabilities import CAPABILITIES, supported_harnesses
    from generate import ADAPTERS, DOC_FILES, ROOT, parse_frontmatter, render_docs


@dataclass
class Finding:
    severity: str
    path: str
    message: str


TRIGGER_RE = re.compile(r"\bUse (?:when|this skill when|PROACTIVELY|after)\b", re.IGNORECASE)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{24,}\b"),
)
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?")


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def add(findings: list[Finding], severity: str, path: Path, message: str) -> None:
    findings.append(Finding(severity, display_path(path), message))


def validate_manifest(findings: list[Finding], path: Path, expected_name: str) -> dict | None:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        add(findings, "error", path, "manifest is missing")
        return None
    except json.JSONDecodeError as exc:
        add(findings, "error", path, f"invalid JSON: {exc}")
        return None

    for field in ("name", "version", "description", "author"):
        if not manifest.get(field):
            add(findings, "error", path, f"missing required field `{field}`")
    if manifest.get("name") != expected_name:
        add(findings, "error", path, f"name must be `{expected_name}`")
    if not SEMVER_RE.fullmatch(str(manifest.get("version", ""))):
        add(findings, "error", path, "version must be SemVer")
    author = manifest.get("author")
    if not isinstance(author, dict) or not author.get("name"):
        add(findings, "error", path, "author.name is required")
    interface = manifest.get("interface", {})
    for field in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
        if not interface.get(field):
            add(findings, "error", path, f"interface.{field} is required")
    if not isinstance(interface.get("capabilities"), list):
        add(findings, "error", path, "interface.capabilities must be an array")
    prompts = interface.get("defaultPrompt")
    if not isinstance(prompts, list) or not prompts or len(prompts) > 3:
        add(findings, "error", path, "interface.defaultPrompt must contain 1-3 prompts")
    return manifest


def validate_source(root: Path, findings: list[Finding]) -> list[str]:
    marketplace_path = root / ".claude-plugin" / "marketplace.json"
    try:
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        add(findings, "error", marketplace_path, "Claude Code marketplace is missing")
        return []
    except json.JSONDecodeError as exc:
        add(findings, "error", marketplace_path, f"invalid JSON: {exc}")
        return []

    metadata = marketplace.get("metadata", {})
    if not isinstance(metadata, dict):
        add(findings, "error", marketplace_path, "metadata must be an object")
        metadata = {}
    if not SEMVER_RE.fullmatch(str(metadata.get("version", ""))):
        add(findings, "error", marketplace_path, "metadata.version must be SemVer")

    plugin_names: list[str] = []
    names: list[str] = []
    for entry in marketplace.get("plugins", []):
        name = entry.get("name", "")
        plugin_names.append(name)
        names.append(name)
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            add(findings, "error", marketplace_path, f"invalid plugin name `{name}`")
        source = entry.get("source")
        if not isinstance(source, str) or not source.startswith("./plugins/"):
            add(findings, "error", marketplace_path, f"{name}: source must be a local ./plugins path")
            continue
        plugin_dir = root / source[2:]
        if not plugin_dir.is_dir():
            add(findings, "error", marketplace_path, f"{name}: source directory is missing")
            continue
        manifest = validate_manifest(findings, plugin_dir / ".claude-plugin" / "plugin.json", name)
        if manifest is None:
            continue
        if entry.get("version") != manifest.get("version"):
            add(
                findings,
                "error",
                marketplace_path,
                f"{name}: marketplace version must match plugin.json version",
            )
        if not (plugin_dir / ".codex-plugin" / "plugin.json").is_file():
            add(findings, "error", plugin_dir, "Codex plugin manifest is missing")
        else:
            try:
                codex_manifest = json.loads(
                    (plugin_dir / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
                )
            except json.JSONDecodeError as exc:
                add(findings, "error", plugin_dir / ".codex-plugin" / "plugin.json", f"invalid JSON: {exc}")
            else:
                if codex_manifest.get("name") != manifest.get("name"):
                    add(findings, "error", plugin_dir / ".codex-plugin" / "plugin.json", "name differs from source manifest")
                if codex_manifest.get("version") != manifest.get("version"):
                    add(findings, "error", plugin_dir / ".codex-plugin" / "plugin.json", "version differs from source manifest")

        for agent_path in sorted((plugin_dir / "agents").glob("*.md")) if (plugin_dir / "agents").is_dir() else []:
            fields, _body = parse_frontmatter(agent_path.read_text(encoding="utf-8"))
            for field in ("name", "description", "model"):
                if not fields.get(field):
                    add(findings, "error", agent_path, f"missing frontmatter field `{field}`")
            if fields.get("name") in {"default", "worker", "explorer"}:
                add(findings, "error", agent_path, "agent name collides with a Codex built-in")
            component_id = f"{name}__{fields.get('name', agent_path.stem)}"
            if component_id in names:
                add(findings, "error", agent_path, f"agent name `{component_id}` is duplicated")
            names.append(component_id)

        skills_dir = plugin_dir / "skills"
        for skill_dir in sorted(path for path in skills_dir.iterdir() if path.is_dir()) if skills_dir.is_dir() else []:
            skill_path = skill_dir / "SKILL.md"
            if not skill_path.is_file():
                add(findings, "error", skill_dir, "SKILL.md is missing")
                continue
            fields, body = parse_frontmatter(skill_path.read_text(encoding="utf-8"))
            for field in ("name", "description"):
                if not fields.get(field):
                    add(findings, "error", skill_path, f"missing frontmatter field `{field}`")
            if fields.get("name") != skill_dir.name:
                add(findings, "error", skill_path, "frontmatter name must match the skill directory")
            if fields.get("description") and not TRIGGER_RE.search(fields["description"]):
                add(findings, "warning", skill_path, "description has no recognized activation phrase")
            if len(body.encode("utf-8")) > 8192 and not (skill_dir / "references").is_dir():
                add(findings, "error", skill_path, "skill body exceeds Codex 8KB cap without references/")

        commands_dir = plugin_dir / "commands"
        for command_path in sorted(commands_dir.glob("*.md")) if commands_dir.is_dir() else []:
            fields, _body = parse_frontmatter(command_path.read_text(encoding="utf-8"))
            if not fields.get("description"):
                add(findings, "error", command_path, "command description is required")

    if len(names) != len(set(names)):
        add(findings, "error", marketplace_path, "plugin and agent names must be globally unique")

    plugins_root = root / "plugins"
    actual_plugins = {
        path.name
        for path in plugins_root.iterdir()
        if path.is_dir() and (path / ".claude-plugin" / "plugin.json").is_file()
    } if plugins_root.is_dir() else set()
    if set(plugin_names) != actual_plugins:
        add(findings, "warning", root / "plugins", "plugin directories and marketplace entries differ")
    return plugin_names


def validate_generated(root: Path, findings: list[Finding], plugin_names: list[str]) -> None:
    codex_marketplace = root / ".agents" / "plugins" / "marketplace.json"
    try:
        data = json.loads(codex_marketplace.read_text(encoding="utf-8"))
    except FileNotFoundError:
        add(findings, "error", codex_marketplace, "run the generator before validating generated artifacts")
        data = {}
    except json.JSONDecodeError as exc:
        add(findings, "error", codex_marketplace, f"invalid JSON: {exc}")
        data = {}

    source_marketplace = root / ".claude-plugin" / "marketplace.json"
    try:
        source_data = json.loads(source_marketplace.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        source_data = {}
    if data.get("metadata", {}).get("version") != source_data.get("metadata", {}).get("version"):
        add(findings, "error", codex_marketplace, "Codex marketplace metadata.version differs from source")

    generated_names = [entry.get("name") for entry in data.get("plugins", [])]
    if generated_names != plugin_names:
        add(findings, "error", codex_marketplace, "Codex marketplace plugin order or names differ from source")
    for entry in data.get("plugins", []):
        source = entry.get("source", {})
        if not isinstance(source, dict):
            add(findings, "error", codex_marketplace, f"{entry.get('name')}: Codex source must be an object")
            continue
        source_path = source.get("path", "")
        if source.get("source") != "local" or not isinstance(source_path, str) or not source_path.startswith("./plugins/"):
            add(findings, "error", codex_marketplace, f"{entry.get('name')}: invalid Codex local source")
        source_manifest = root / source_path / ".claude-plugin" / "plugin.json" if isinstance(source_path, str) else root / "__missing__"
        if source_manifest.is_file():
            try:
                manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if entry.get("version") != manifest.get("version"):
                add(findings, "error", codex_marketplace, f"{entry.get('name')}: version differs from source manifest")

    for directory, label in ((root / ".codex" / "agents", "Codex agents"), (root / ".codex" / "skills", "Codex skills"), (root / ".opencode" / "agents", "OpenCode agents"), (root / ".opencode" / "skills", "OpenCode skills"), (root / ".opencode" / "commands", "OpenCode commands")):
        if not directory.is_dir() or not any(directory.iterdir()):
            add(findings, "error", directory, f"{label} output is missing; run the generator")
    if not (root / "opencode.json").is_file():
        add(findings, "error", root / "opencode.json", "OpenCode config is missing")

    for path in (root / ".codex" / "skills").glob("*/SKILL.md") if (root / ".codex" / "skills").is_dir() else []:
        if len(path.read_bytes()) > 8192:
            add(findings, "error", path, "generated Codex Skill exceeds 8KB")
    for path in (root / ".opencode" / "agents").glob("*.md") if (root / ".opencode" / "agents").is_dir() else []:
        content = path.read_text(encoding="utf-8")
        if "mode: \"subagent\"" not in content or "permission:" not in content:
            add(findings, "error", path, "OpenCode agent is missing mode or permission block")

    source_marketplace_data = source_data if isinstance(source_data, dict) else {}
    required = {
        "cursor": (root / ".cursor-plugin" / "marketplace.json", root / ".cursor-plugin" / "plugin.json"),
        "gemini": (root / "gemini-extension.json",),
        "copilot": (root / ".copilot",),
    }
    for harness_id, paths in required.items():
        for path in paths:
            if not path.exists():
                add(findings, "error", path, f"{harness_id} output is missing; run the generator")

    cursor_marketplace = root / ".cursor-plugin" / "marketplace.json"
    if cursor_marketplace.is_file():
        try:
            cursor_data = json.loads(cursor_marketplace.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            add(findings, "error", cursor_marketplace, f"invalid JSON: {exc}")
            cursor_data = {}
        if [entry.get("name") for entry in cursor_data.get("plugins", [])] != plugin_names:
            add(findings, "error", cursor_marketplace, "Cursor marketplace plugin order or names differ from source")
        for plugin_name in plugin_names:
            manifest = root / "plugins" / plugin_name / ".claude-plugin" / "plugin.json"
            cursor_plugin = root / ".cursor-plugin" / "plugins" / f"{plugin_name}.json"
            if not cursor_plugin.is_file():
                add(findings, "error", cursor_plugin, "Cursor plugin manifest is missing")
            elif manifest.is_file():
                source_manifest = json.loads(manifest.read_text(encoding="utf-8"))
                generated_manifest = json.loads(cursor_plugin.read_text(encoding="utf-8"))
                if generated_manifest.get("version") != source_manifest.get("version"):
                    add(findings, "error", cursor_plugin, "version differs from source manifest")

    extension_path = root / "gemini-extension.json"
    if extension_path.is_file():
        try:
            extension = json.loads(extension_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            add(findings, "error", extension_path, f"invalid JSON: {exc}")
            extension = {}
        if extension.get("version") != source_marketplace_data.get("metadata", {}).get("version"):
            add(findings, "error", extension_path, "version differs from marketplace metadata")
        for plugin_name in plugin_names:
            plugin_dir = root / "plugins" / plugin_name
            for agent_path in (plugin_dir / "agents").glob("*.md") if (plugin_dir / "agents").is_dir() else []:
                fields, _ = parse_frontmatter(agent_path.read_text(encoding="utf-8"))
                output = root / "agents" / f"{plugin_name}__{fields.get('name', agent_path.stem)}.md"
                if not output.is_file():
                    add(findings, "error", output, "Gemini agent output is missing")
            for skill_dir in (path for path in (plugin_dir / "skills").iterdir() if path.is_dir()) if (plugin_dir / "skills").is_dir() else []:
                fields, _ = parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8")) if (skill_dir / "SKILL.md").is_file() else ({}, "")
                output = root / "skills" / f"{plugin_name}__{fields.get('name', skill_dir.name)}" / "SKILL.md"
                if not output.is_file():
                    add(findings, "error", output, "Gemini skill output is missing")
            for command_path in (plugin_dir / "commands").glob("*.md") if (plugin_dir / "commands").is_dir() else []:
                output = root / "commands" / plugin_name / f"{command_path.stem}.toml"
                if not output.is_file():
                    add(findings, "error", output, "Gemini command output is missing")

    if not (root / ".copilot" / "agents").is_dir() or not any((root / ".copilot" / "agents").iterdir()):
        add(findings, "error", root / ".copilot" / "agents", "Copilot agent output is missing")

    if set(ADAPTERS) != set(supported_harnesses()):
        add(findings, "error", root / "tools", "adapter registry and supported harness list differ")
    if not set(supported_harnesses()).issubset(CAPABILITIES):
        add(findings, "error", root / "tools/adapters/capabilities.py", "capability matrix is missing a supported harness")

    try:
        expected_docs = render_docs(root)
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as exc:
        add(findings, "error", root / "docs", f"cannot render generated documentation: {exc}")
        expected_docs = {}
    for relative_path, expected in expected_docs.items():
        path = root / relative_path
        if not path.is_file():
            add(findings, "error", path, "generated documentation is missing")
        elif path.read_text(encoding="utf-8") != expected:
            add(findings, "error", path, "generated documentation is out of date")


def scan_secrets(root: Path, findings: list[Finding]) -> None:
    for path in root.glob("**/*"):
        if not path.is_file() or ".git" in path.parts or path.parts[-1] in {"validate.py", "generate.py"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                add(findings, "error", path, "possible credential material found")
                break


def validate_repo(root: Path = ROOT, *, require_generated: bool = True) -> list[Finding]:
    findings: list[Finding] = []
    context = root / "AGENTS.md"
    if context.is_file() and len(context.read_text(encoding="utf-8").splitlines()) > 150:
        add(findings, "error", context, "AGENTS.md exceeds the 150-line context budget")
    changelog = root / "CHANGELOG.md"
    try:
        marketplace = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        marketplace = {}
    current_version = marketplace.get("metadata", {}).get("version")
    if not changelog.is_file():
        add(findings, "error", changelog, "CHANGELOG.md is missing")
    elif current_version and f"## [{current_version}]" not in changelog.read_text(encoding="utf-8"):
        add(findings, "error", changelog, f"current marketplace version {current_version} has no CHANGELOG entry")
    plugin_names = validate_source(root, findings)
    if require_generated:
        validate_generated(root, findings, plugin_names)
    scan_secrets(root, findings)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-generated", action="store_true", help="Validate only source files.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors.")
    args = parser.parse_args()
    findings = validate_repo(ROOT, require_generated=not args.no_generated)
    for finding in findings:
        print(f"[{finding.severity}] {finding.path}: {finding.message}")
    errors = sum(f.severity == "error" for f in findings)
    warnings = sum(f.severity == "warning" for f in findings)
    print(f"Validation: {errors} error(s), {warnings} warning(s).")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())

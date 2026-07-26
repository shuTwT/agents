#!/usr/bin/env python3
"""Recurring repository hygiene checks for the plugin marketplace."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from .generate import ROOT, find_generated_drift
except ImportError:  # pragma: no cover - direct script compatibility
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools.generate import ROOT, find_generated_drift


@dataclass
class GardenFinding:
    kind: str
    severity: str
    path: Path
    message: str
    fix: str

    def render(self, root: Path) -> str:
        try:
            relative = self.path.relative_to(root)
        except ValueError:
            relative = self.path
        return f"[{self.severity:7}] {self.kind:24} {relative}: {self.message}\n           Fix: {self.fix}"


SEMVER_RE = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?")
LINK_RE = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")


def add(findings: list[GardenFinding], root: Path, kind: str, severity: str, path: Path, message: str, fix: str) -> None:
    findings.append(GardenFinding(kind, severity, path, message, fix))


def check_drift(root: Path, findings: list[GardenFinding]) -> None:
    differences = find_generated_drift(root)
    for difference in differences:
        add(
            findings,
            root,
            "generated-drift",
            "error",
            root,
            difference,
            "Run `make generate-all` and commit only the lightweight registries and catalogs.",
        )


def check_context(root: Path, findings: list[GardenFinding]) -> None:
    limits = {"AGENTS.md": 150, "CLAUDE.md": 200}
    for filename, limit in limits.items():
        path = root / filename
        if path.is_file() and len(path.read_text(encoding="utf-8").splitlines()) > limit:
            add(findings, root, "context-size", "error", path, f"contains more than {limit} lines", f"Move detailed guidance into references or plugin documentation.")


def check_skill_caps(root: Path, findings: list[GardenFinding]) -> None:
    for path in root.glob("plugins/*/skills/*/SKILL.md"):
        fields_end = path.read_text(encoding="utf-8").find("\n---", 3)
        body = path.read_text(encoding="utf-8")[fields_end + 4 :] if fields_end >= 0 else path.read_text(encoding="utf-8")
        if len(body.encode("utf-8")) > 8192 and not (path.parent / "references").is_dir():
            add(findings, root, "skill-cap", "error", path, "source skill body exceeds Codex 8KB cap without references/", "Move detailed material into references/.")
    for path in root.glob(".codex/skills/*/SKILL.md"):
        if len(path.read_bytes()) > 8192:
            add(findings, root, "generated-skill-cap", "error", path, "generated Codex Skill exceeds 8KB", "Split the skill body and keep details in references/.")


def check_marketplace(root: Path, findings: list[GardenFinding]) -> None:
    marketplace_path = root / ".claude-plugin/marketplace.json"
    try:
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return
    entries = {entry.get("name") for entry in marketplace.get("plugins", [])}
    plugins_root = root / "plugins"
    actual = {
        path.name
        for path in plugins_root.iterdir()
        if path.is_dir() and (path / ".claude-plugin/plugin.json").is_file()
    } if plugins_root.is_dir() else set()
    for missing in sorted(actual - entries):
        add(findings, root, "marketplace-drift", "error", plugins_root / missing, "plugin directory is not listed in marketplace", "Add a matching ./plugins/<name> entry.")
    for extra in sorted(entries - actual):
        add(findings, root, "marketplace-drift", "error", marketplace_path, f"marketplace entry `{extra}` has no source directory", "Remove the entry or restore its plugin directory.")
    version = marketplace.get("metadata", {}).get("version", "")
    if not SEMVER_RE.fullmatch(str(version)):
        add(findings, root, "marketplace-version", "error", marketplace_path, "metadata.version is not SemVer", "Update metadata.version and CHANGELOG.md.")


def check_dead_links(root: Path, findings: list[GardenFinding]) -> None:
    for path in root.glob("**/*.md"):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        content = path.read_text(encoding="utf-8")
        for target in LINK_RE.findall(content):
            target = target.strip().split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:", "/")):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                add(findings, root, "dead-link", "warning", path, f"relative link target `{target}` does not exist", "Fix the link or remove it.")


def check_component_collisions(root: Path, findings: list[GardenFinding]) -> None:
    try:
        marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return
    opencode_skills: dict[str, Path] = {}
    for entry in marketplace.get("plugins", []):
        name = entry.get("name", "")
        plugin_dir = root / "plugins" / name
        skills_dir = plugin_dir / "skills"
        if not skills_dir.is_dir():
            continue
        for skill_dir in (path for path in skills_dir.iterdir() if path.is_dir()):
            identifier = f"{name}-{skill_dir.name}"
            previous = opencode_skills.get(identifier)
            if previous and previous != skill_dir:
                add(findings, root, "component-collision", "error", skill_dir, f"OpenCode skill id `{identifier}` collides with {previous.relative_to(root)}", "Rename one plugin or skill to make the generated id unique.")
            opencode_skills[identifier] = skill_dir


def run_garden(root: Path = ROOT) -> list[GardenFinding]:
    findings: list[GardenFinding] = []
    check_drift(root, findings)
    check_context(root, findings)
    check_skill_caps(root, findings)
    check_marketplace(root, findings)
    check_dead_links(root, findings)
    check_component_collisions(root, findings)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors.")
    args = parser.parse_args()
    findings = run_garden(ROOT)
    for finding in findings:
        print(finding.render(ROOT))
    errors = sum(finding.severity == "error" for finding in findings)
    warnings = sum(finding.severity == "warning" for finding in findings)
    print(f"Garden: {errors} error(s), {warnings} warning(s).")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())

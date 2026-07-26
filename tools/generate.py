#!/usr/bin/env python3
"""Generate marketplace documentation and harness artifacts.

The files under ``plugins/`` and ``.claude-plugin/marketplace.json`` are the
canonical sources.  Generated output can be rendered into another directory,
which lets ``--check`` detect drift without modifying the working tree.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = "plugins"
MARKETPLACE = ".claude-plugin/marketplace.json"
DOC_FILES = (
    "docs/plugins.md",
    "docs/agents.md",
    "docs/skills.md",
    "docs/commands.md",
)

MODEL_MAP = {
    "inherit": "anthropic/claude-sonnet-5",
    "opus": "anthropic/claude-opus-4-8",
    "sonnet": "anthropic/claude-sonnet-5",
    "haiku": "anthropic/claude-haiku-4-5",
}

CODEX_MODEL_MAP = {
    "inherit": "gpt-5.4-mini",
    "opus": "gpt-5.5",
    "sonnet": "gpt-5.4-mini",
    "haiku": "gpt-5.4-mini",
}

TOOL_REPLACEMENTS = {
    "Read": "open the file",
    "Edit": "edit the file",
    "Write": "create the file",
    "Bash": "run the shell command",
    "Grep": "search for the pattern",
    "Glob": "find matching files",
    "Task": "delegate to a subagent",
    "Agent": "delegate to a subagent",
    "TodoWrite": "track progress",
}


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse the small scalar frontmatter subset used by this repository."""
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---", 4)
    if end == -1:
        return {}, content

    fields: dict[str, str] = {}
    for line in content[4:end].splitlines():
        if not line.strip() or line.startswith((" ", "\t")):
            continue
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields, content[end + 4 :].lstrip("\n")


def render_frontmatter(fields: dict[str, str]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {json.dumps(str(value), ensure_ascii=False)}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def rewrite_tool_references(body: str, *, style: str) -> str:
    """Rewrite explicit Claude tool vocabulary into target-harness prose."""
    output = body
    for tool, replacement in TOOL_REPLACEMENTS.items():
        if style == "opencode":
            replacement = tool.lower() if tool not in {"Task", "Agent"} else "task"
        if style == "codex":
            pattern = rf"(?i:\bthe)\s+`?{re.escape(tool)}`?\s+tool\b"
            output = re.sub(pattern, replacement, output)
        else:
            output = output.replace(f"`{tool}`", f"`{replacement}")
            output = output.replace(f"{tool} tool", f"{replacement} tool")
    return output


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def marketplace_data(root: Path = ROOT) -> dict:
    return read_json(root / MARKETPLACE)


def source_plugins(root: Path = ROOT) -> list[tuple[Path, dict]]:
    plugins_root = root / PLUGINS
    if not plugins_root.is_dir():
        return []
    result: list[tuple[Path, dict]] = []
    for plugin_dir in sorted(path for path in plugins_root.iterdir() if path.is_dir()):
        manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
        if manifest_path.is_file():
            result.append((plugin_dir, read_json(manifest_path)))
    return result


def marketplace_entries(root: Path = ROOT) -> dict[str, dict]:
    return {
        entry["name"]: entry
        for entry in marketplace_data(root).get("plugins", [])
        if entry.get("name")
    }


def copy_support_files(source: Path, destination: Path) -> None:
    for directory in ("references", "assets"):
        source_dir = source / directory
        if source_dir.is_dir():
            shutil.copytree(source_dir, destination / directory, dirs_exist_ok=True)


def iter_agents(plugin_dir: Path):
    agent_dir = plugin_dir / "agents"
    return sorted(agent_dir.glob("*.md")) if agent_dir.is_dir() else []


def iter_skills(plugin_dir: Path):
    skills_dir = plugin_dir / "skills"
    return (
        sorted(path for path in skills_dir.iterdir() if path.is_dir())
        if skills_dir.is_dir()
        else []
    )


def iter_commands(plugin_dir: Path):
    commands_dir = plugin_dir / "commands"
    return sorted(commands_dir.glob("*.md")) if commands_dir.is_dir() else []


def generate_codex(root: Path = ROOT) -> int:
    output_root = root / ".codex"
    shutil.rmtree(output_root, ignore_errors=True)
    (output_root / "agents").mkdir(parents=True, exist_ok=True)
    (output_root / "skills").mkdir(parents=True, exist_ok=True)

    marketplace = marketplace_data(root)
    entries = marketplace_entries(root)
    codex_marketplace = {
        "name": marketplace["name"],
        "metadata": marketplace.get("metadata", {}),
        "plugins": [],
    }
    written = 0

    for plugin_dir, manifest in source_plugins(root):
        plugin_name = manifest["name"]
        entry = entries.get(plugin_name, {})
        codex_manifest = dict(manifest)
        codex_manifest["skills"] = "./skills/"
        write_json(plugin_dir / ".codex-plugin" / "plugin.json", codex_manifest)
        written += 1

        codex_marketplace["plugins"].append(
            {
                "name": plugin_name,
                "description": manifest["description"],
                "version": manifest["version"],
                "author": manifest.get("author", {}),
                "source": {"source": "local", "path": f"./plugins/{plugin_name}"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": entry.get(
                    "category", manifest.get("interface", {}).get("category", "Coding")
                ),
            }
        )

        for agent_path in iter_agents(plugin_dir):
            fields, body = parse_frontmatter(agent_path.read_text(encoding="utf-8"))
            agent_name = f"{plugin_name}__{fields.get('name', agent_path.stem)}"
            model = CODEX_MODEL_MAP.get(fields.get("model", "inherit"), CODEX_MODEL_MAP["inherit"])
            description = fields.get("description", "")
            instructions = rewrite_tool_references(body, style="codex")
            toml = (
                f"name = {json.dumps(agent_name)}\n"
                f"description = {json.dumps(description, ensure_ascii=False)}\n"
                f"model = {json.dumps(model)}\n"
                'sandbox_mode = "workspace-write"\n'
                "developer_instructions = \"\"\"\n"
                f"{instructions.replace(chr(34) * 3, '\\"\\"\\"')}\n"
                "\"\"\"\n"
            )
            write_text(output_root / "agents" / f"{agent_name}.toml", toml)
            written += 1

        for skill_dir in iter_skills(plugin_dir):
            skill_path = skill_dir / "SKILL.md"
            if not skill_path.is_file():
                continue
            fields, body = parse_frontmatter(skill_path.read_text(encoding="utf-8"))
            skill_name = f"{plugin_name}__{fields.get('name', skill_dir.name)}"
            content = render_frontmatter(
                {"name": skill_name, "description": fields.get("description", "")}
            )
            content += rewrite_tool_references(body, style="codex")
            destination = output_root / "skills" / skill_name
            write_text(destination / "SKILL.md", content)
            copy_support_files(skill_dir, destination)
            written += 1

        for command_path in iter_commands(plugin_dir):
            fields, body = parse_frontmatter(command_path.read_text(encoding="utf-8"))
            skill_name = f"{plugin_name}__{command_path.stem}__command"
            content = render_frontmatter(
                {"name": skill_name, "description": fields.get("description", "")}
            )
            content += rewrite_tool_references(body, style="codex")
            write_text(output_root / "skills" / skill_name / "SKILL.md", content)
            written += 1

    write_json(root / ".agents" / "plugins" / "marketplace.json", codex_marketplace)
    return written + 1


def opencode_permission_block() -> str:
    permissions = [
        "read",
        "edit",
        "write",
        "bash",
        "grep",
        "glob",
        "list",
        "task",
        "skill",
        "webfetch",
        "websearch",
    ]
    return "\n".join(f"  {permission}: allow" for permission in permissions)


def render_opencode_frontmatter(fields: dict[str, str]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {json.dumps(str(value), ensure_ascii=False)}")
    lines.append("permission:")
    lines.extend(opencode_permission_block().splitlines())
    lines.extend(["---", ""])
    return "\n".join(lines)


def generate_opencode(root: Path = ROOT) -> int:
    output_root = root / ".opencode"
    shutil.rmtree(output_root, ignore_errors=True)
    written = 0

    for plugin_dir, _manifest in source_plugins(root):
        plugin_name = plugin_dir.name
        for agent_path in iter_agents(plugin_dir):
            fields, body = parse_frontmatter(agent_path.read_text(encoding="utf-8"))
            name = f"{plugin_name}__{fields.get('name', agent_path.stem)}"
            frontmatter = render_opencode_frontmatter(
                {
                    "description": fields.get("description", ""),
                    "mode": "subagent",
                    "model": MODEL_MAP.get(fields.get("model", "inherit"), MODEL_MAP["inherit"]),
                }
            )
            write_text(
                output_root / "agents" / f"{name}.md",
                frontmatter + rewrite_tool_references(body, style="opencode"),
            )
            written += 1

        for skill_dir in iter_skills(plugin_dir):
            skill_path = skill_dir / "SKILL.md"
            if not skill_path.is_file():
                continue
            fields, body = parse_frontmatter(skill_path.read_text(encoding="utf-8"))
            name = f"{plugin_name}-{skill_dir.name}"
            content = render_frontmatter(
                {"name": name, "description": fields.get("description", "")}
            )
            destination = output_root / "skills" / name
            write_text(
                destination / "SKILL.md",
                content + rewrite_tool_references(body, style="opencode"),
            )
            copy_support_files(skill_dir, destination)
            written += 1

        for command_path in iter_commands(plugin_dir):
            fields, body = parse_frontmatter(command_path.read_text(encoding="utf-8"))
            content = render_frontmatter(
                {
                    "description": fields.get("description", ""),
                    "argument-hint": fields.get("argument-hint", ""),
                }
            )
            write_text(
                output_root / "commands" / f"{plugin_name}__{command_path.stem}.md",
                content + rewrite_tool_references(body, style="opencode"),
            )
            written += 1

    write_json(root / "opencode.json", {"$schema": "https://opencode.ai/config.json"})
    return written + 1


def markdown_cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def source_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def render_docs(root: Path = ROOT) -> dict[str, str]:
    marketplace = marketplace_data(root)
    entries = marketplace_entries(root)
    plugins = source_plugins(root)

    plugin_lines = [
        "# 插件目录",
        "",
        "> 本文件由 `tools/generate.py` 生成，请修改 `plugins/` 和 marketplace 源文件。",
        "",
        "| 插件 | 版本 | 类别 | 描述 | 能力 |",
        "| --- | --- | --- | --- | --- |",
    ]
    agent_lines = [
        "# Agent 目录",
        "",
        "> 本文件由 `tools/generate.py` 生成。",
        "",
        "| 名称 | 插件 | 模型 | 描述 | 源文件 |",
        "| --- | --- | --- | --- | --- |",
    ]
    skill_lines = [
        "# Skill 目录",
        "",
        "> 本文件由 `tools/generate.py` 生成。",
        "",
        "| 名称 | 插件 | 描述 | references | assets | 源文件 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    command_lines = [
        "# Command 目录",
        "",
        "> 本文件由 `tools/generate.py` 生成。",
        "",
        "| 名称 | 插件 | 描述 | 参数提示 | 源文件 |",
        "| --- | --- | --- | --- | --- |",
    ]

    for plugin_dir, manifest in plugins:
        plugin_name = manifest["name"]
        entry = entries.get(plugin_name, {})
        capabilities = ", ".join(manifest.get("interface", {}).get("capabilities", []))
        plugin_lines.append(
            "| "
            + " | ".join(
                map(
                    markdown_cell,
                    (
                        f"`{plugin_name}`",
                        manifest.get("version"),
                        entry.get("category", manifest.get("interface", {}).get("category")),
                        manifest.get("description"),
                        capabilities,
                    ),
                )
            )
            + " |"
        )

        for agent_path in iter_agents(plugin_dir):
            fields, _body = parse_frontmatter(agent_path.read_text(encoding="utf-8"))
            agent_lines.append(
                "| "
                + " | ".join(
                    map(
                        markdown_cell,
                        (
                            f"`{plugin_name}__{fields.get('name', agent_path.stem)}`",
                            f"`{plugin_name}`",
                            fields.get("model", "inherit"),
                            fields.get("description"),
                            f"`{source_path(root, agent_path)}`",
                        ),
                    )
                )
                + " |"
            )

        for skill_dir in iter_skills(plugin_dir):
            skill_path = skill_dir / "SKILL.md"
            if not skill_path.is_file():
                continue
            fields, _body = parse_frontmatter(skill_path.read_text(encoding="utf-8"))
            skill_lines.append(
                "| "
                + " | ".join(
                    map(
                        markdown_cell,
                        (
                            f"`{plugin_name}__{fields.get('name', skill_dir.name)}`",
                            f"`{plugin_name}`",
                            fields.get("description"),
                            "yes" if (skill_dir / "references").is_dir() else "no",
                            "yes" if (skill_dir / "assets").is_dir() else "no",
                            f"`{source_path(root, skill_path)}`",
                        ),
                    )
                )
                + " |"
            )

        for command_path in iter_commands(plugin_dir):
            fields, _body = parse_frontmatter(command_path.read_text(encoding="utf-8"))
            command_lines.append(
                "| "
                + " | ".join(
                    map(
                        markdown_cell,
                        (
                            f"`{plugin_name}__{command_path.stem}`",
                            f"`{plugin_name}`",
                            fields.get("description"),
                            fields.get("argument-hint", ""),
                            f"`{source_path(root, command_path)}`",
                        ),
                    )
                )
                + " |"
            )

    return {
        DOC_FILES[0]: "\n".join(plugin_lines) + "\n",
        DOC_FILES[1]: "\n".join(agent_lines) + "\n",
        DOC_FILES[2]: "\n".join(skill_lines) + "\n",
        DOC_FILES[3]: "\n".join(command_lines) + "\n",
    }


def generate_docs(root: Path = ROOT) -> int:
    rendered = render_docs(root)
    docs_root = root / "docs"
    docs_root.mkdir(parents=True, exist_ok=True)
    for relative_path, content in rendered.items():
        write_text(root / relative_path, content)
    return len(rendered)


def generate(root: Path = ROOT, *, harness: str = "all", docs: bool | None = None) -> int:
    if docs is None:
        docs = harness == "all"
    written = 0
    if harness in ("codex", "all"):
        written += generate_codex(root)
    if harness in ("opencode", "all"):
        written += generate_opencode(root)
    if docs:
        written += generate_docs(root)
    return written


def clean_generated(root: Path = ROOT, *, harness: str = "all", docs: bool | None = None) -> None:
    if docs is None:
        docs = harness == "all"
    if harness in ("codex", "all"):
        shutil.rmtree(root / ".codex", ignore_errors=True)
        marketplace = root / ".agents" / "plugins" / "marketplace.json"
        if marketplace.exists():
            marketplace.unlink()
        for plugin_dir, _manifest in source_plugins(root):
            codex_manifest = plugin_dir / ".codex-plugin" / "plugin.json"
            if codex_manifest.exists():
                codex_manifest.unlink()
    if harness in ("opencode", "all"):
        shutil.rmtree(root / ".opencode", ignore_errors=True)
        opencode_config = root / "opencode.json"
        if opencode_config.exists():
            opencode_config.unlink()
    if docs:
        for relative_path in DOC_FILES:
            path = root / relative_path
            if path.exists():
                path.unlink()


def generated_relative_paths(root: Path, *, harness: str = "all", docs: bool = False) -> set[str]:
    paths: set[str] = set()

    def add_files(directory: Path) -> None:
        if directory.is_dir():
            paths.update(path.relative_to(root).as_posix() for path in directory.rglob("*") if path.is_file())

    if harness in ("codex", "all"):
        add_files(root / ".codex")
        marketplace = root / ".agents" / "plugins" / "marketplace.json"
        if marketplace.is_file():
            paths.add(marketplace.relative_to(root).as_posix())
        for plugin_dir, _manifest in source_plugins(root):
            manifest = plugin_dir / ".codex-plugin" / "plugin.json"
            if manifest.is_file():
                paths.add(manifest.relative_to(root).as_posix())
    if harness in ("opencode", "all"):
        add_files(root / ".opencode")
        opencode_config = root / "opencode.json"
        if opencode_config.is_file():
            paths.add(opencode_config.relative_to(root).as_posix())
    if docs:
        paths.update(DOC_FILES)
    return paths


def check_generated(root: Path = ROOT, *, harness: str = "all", docs: bool | None = None) -> int:
    if docs is None:
        docs = harness == "all"
    with tempfile.TemporaryDirectory(prefix="agent-marketplace-check-") as temporary:
        staged_root = Path(temporary) / "repo"
        shutil.copytree(
            root,
            staged_root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"),
        )
        generate(staged_root, harness=harness, docs=docs)
        expected_paths = generated_relative_paths(staged_root, harness=harness, docs=docs)
        actual_paths = generated_relative_paths(root, harness=harness, docs=docs)

        differences = False
        for relative_path in sorted(expected_paths - actual_paths):
            print(f"[missing] {relative_path}")
            differences = True
        for relative_path in sorted(actual_paths - expected_paths):
            print(f"[extra] {relative_path}")
            differences = True
        for relative_path in sorted(expected_paths & actual_paths):
            expected = (staged_root / relative_path).read_bytes()
            actual = (root / relative_path).read_bytes()
            if expected != actual:
                print(f"[changed] {relative_path}")
                differences = True
        if differences:
            print("Generated artifacts are out of date. Run `make generate-all` and commit the result.")
            return 1
    print(f"Generated artifacts are up to date for {harness}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", choices=("codex", "opencode", "all"), default="all")
    parser.add_argument("--docs-only", action="store_true", help="Generate or check only marketplace documentation.")
    parser.add_argument("--check", action="store_true", help="Check generated files without modifying the working tree.")
    parser.add_argument("--clean", action="store_true", help="Remove selected generated artifacts and exit.")
    args = parser.parse_args()

    if args.docs_only and args.clean and args.harness != "all":
        parser.error("--docs-only cannot be combined with --harness codex/opencode")
    if args.clean and args.check:
        parser.error("--clean cannot be combined with --check")

    harness = "none" if args.docs_only else args.harness
    docs = True if args.docs_only else harness == "all"

    if args.clean:
        clean_generated(ROOT, harness=harness, docs=docs)
        print(f"Cleaned generated artifacts for {'docs' if args.docs_only else harness}.")
        return 0
    if args.check:
        return check_generated(ROOT, harness=harness, docs=docs)

    written = generate(ROOT, harness=harness, docs=docs)
    print(f"Generated {written} artifact(s) for {'docs' if args.docs_only else harness}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

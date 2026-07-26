"""Shared source models, parsing helpers, and adapter primitives."""

from __future__ import annotations

import json
import re
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from .capabilities import TOOL_NAME_MAPS, resolve_model

WORKTREE = Path(__file__).resolve().parents[2]
PLUGINS_DIR = WORKTREE / "plugins"


def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _split_inline_list(value: str) -> list[str]:
    items: list[str] = []
    buffer: list[str] = []
    quote: str | None = None
    for char in value:
        if quote:
            if char == quote:
                quote = None
            else:
                buffer.append(char)
        elif char in {'"', "'"}:
            quote = char
        elif char == ",":
            item = "".join(buffer).strip()
            if item:
                items.append(item)
            buffer = []
        else:
            buffer.append(char)
    item = "".join(buffer).strip()
    if item:
        items.append(item)
    return items


def _parse_scalar(value: str):
    value = value.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        return _split_inline_list(value[1:-1].strip())
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "~"}:
        return None
    return value.strip('"').strip("'")


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse the small YAML subset needed by portable plugin source files.

    Supported values are scalars, inline lists, block lists, booleans and one-level
    mappings.  This intentionally avoids a runtime YAML dependency.
    """
    if not content.startswith("---"):
        return {}, content
    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    fields: dict = {}
    current_key: str | None = None
    list_mode = False
    block_scalar = False
    for line in content[3:end].lstrip("\n").splitlines():
        match = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if match:
            current_key = match.group(1)
            raw = match.group(2).strip()
            if raw in {">", ">-", "|", "|-"}:
                fields[current_key] = ""
                block_scalar = True
                list_mode = False
            elif raw in {"", "["}:
                fields[current_key] = [] if raw == "[" else ""
                list_mode = True
                block_scalar = False
            else:
                fields[current_key] = _parse_scalar(raw)
                list_mode = False
                block_scalar = False
            continue

        if current_key is None:
            continue
        if block_scalar and (line.startswith(("  ", "\t")) or not line.strip()):
            value = line.strip()
            if value:
                previous = str(fields.get(current_key, ""))
                fields[current_key] = f"{previous} {value}".strip()
            continue
        if list_mode and line.startswith(("  ", "\t")):
            stripped = line.strip()
            if stripped.startswith("-"):
                if not isinstance(fields[current_key], list):
                    fields[current_key] = []
                item = stripped[1:].strip()
                if item:
                    fields[current_key].append(_parse_scalar(item))
            elif isinstance(fields[current_key], dict):
                nested = re.match(r"^(\w[\w-]*):\s*(.*)$", stripped)
                if nested:
                    fields[current_key][nested.group(1)] = _parse_scalar(nested.group(2))
        elif isinstance(fields.get(current_key), str) and line.startswith("  "):
            fields[current_key] += " " + line.strip()

    return fields, content[end + 4 :].lstrip("\n")


def h1_from_body(body: str) -> str:
    for line in body.splitlines():
        if line.strip().startswith("# "):
            return line.strip()[2:].strip()
    return ""


def context_paragraph(body: str, max_chars: int = 300) -> str:
    """Return a compact first prose paragraph for target manifest summaries."""
    paragraphs = re.split(r"\n\s*\n", body.strip())
    for paragraph in paragraphs:
        text = " ".join(
            line.strip()
            for line in paragraph.splitlines()
            if line.strip() and not line.lstrip().startswith(("#", "```"))
        )
        if text:
            return text[:max_chars].rstrip()
    return ""


def token_estimate(text: str) -> int:
    """Cheap deterministic estimate used by static tooling."""
    return max(1, (len(text) + 3) // 4) if text else 0


def normalize_tools(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def render_frontmatter(fields: dict, *, include_permission: bool = False) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, list):
            rendered = "[" + ", ".join(str(item) for item in value) + "]"
            lines.append(f"{key}: {rendered}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {json.dumps(str(value), ensure_ascii=False)}")
    if include_permission:
        lines.append("permission:")
        for permission in ("read", "edit", "write", "bash", "grep", "glob", "list", "task", "skill", "webfetch", "websearch"):
            lines.append(f"  {permission}: allow")
    lines.extend(["---", ""])
    return "\n".join(lines)


def rewrite_tool_references(body: str, harness_id: str) -> str:
    """Rewrite explicit source tool names into the target harness vocabulary."""
    output = body
    mapping = TOOL_NAME_MAPS.get(harness_id, {})
    for tool, replacement in mapping.items():
        if harness_id == "codex":
            pattern = rf"(?i:\bthe)\s+`?{re.escape(tool)}`?\s+tool\b"
            output = re.sub(pattern, replacement, output)
        else:
            output = output.replace(f"`{tool}`", f"`{replacement}")
            output = output.replace(f"{tool} tool", f"{replacement} tool")
    return output


def resolve_agent_model(agent: AgentSource, harness_id: str, result: EmitResult) -> str:
    model, warning = resolve_model(harness_id, agent.model)
    if warning:
        result.warnings.append(f"agent `{agent.plugin}__{agent.name}`: {warning}")
    return model


@dataclass
class AgentSource:
    plugin: str
    name: str
    path: Path
    frontmatter: dict
    body: str

    @property
    def description(self) -> str:
        return str(self.frontmatter.get("description", "") or "").strip()

    @property
    def model(self) -> str:
        return str(self.frontmatter.get("model", "inherit") or "inherit").strip()

    @property
    def tools(self) -> list[str]:
        return normalize_tools(self.frontmatter.get("tools", self.frontmatter.get("allowed-tools", [])))

    @property
    def color(self) -> str:
        return str(self.frontmatter.get("color", "") or "").strip()


@dataclass
class SkillSource:
    plugin: str
    name: str
    dir: Path
    frontmatter: dict
    body: str

    @property
    def description(self) -> str:
        return str(self.frontmatter.get("description", "") or "").strip()

    @property
    def references_dir(self) -> Path | None:
        path = self.dir / "references"
        return path if path.is_dir() else None

    @property
    def assets_dir(self) -> Path | None:
        path = self.dir / "assets"
        return path if path.is_dir() else None

    @property
    def path(self) -> Path:
        """Local compatibility alias for the canonical SKILL.md file."""
        return self.dir / "SKILL.md"

    @property
    def body_bytes(self) -> int:
        return len(self.body.encode("utf-8"))


@dataclass
class CommandSource:
    plugin: str
    name: str
    path: Path
    frontmatter: dict
    body: str

    @property
    def description(self) -> str:
        return str(self.frontmatter.get("description", "") or "").strip()

    @property
    def argument_hint(self) -> str:
        return str(self.frontmatter.get("argument-hint", "") or "").strip()


@dataclass
class PluginSource:
    name: str
    dir: Path
    plugin_json: dict
    agents: list[AgentSource] = field(default_factory=list)
    skills: list[SkillSource] = field(default_factory=list)
    commands: list[CommandSource] = field(default_factory=list)
    marketplace_entry: dict = field(default_factory=dict)

    @property
    def version(self) -> str:
        return str(self.plugin_json.get("version", ""))

    @property
    def description(self) -> str:
        return str(self.plugin_json.get("description", "") or "").strip()

    @property
    def author(self) -> dict:
        return self.plugin_json.get("author", {}) or {}

    @property
    def interface(self) -> dict:
        return self.plugin_json.get("interface", {}) or {}

    @property
    def path(self) -> Path:
        """Local compatibility alias for the plugin directory."""
        return self.dir


@dataclass
class EmitResult:
    written: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def extend(self, other: "EmitResult") -> None:
        self.written.extend(other.written)
        self.skipped.extend(other.skipped)
        self.warnings.extend(other.warnings)


def _component_files(plugin_dir: Path) -> tuple[list[AgentSource], list[SkillSource], list[CommandSource]]:
    agents: list[AgentSource] = []
    for path in sorted((plugin_dir / "agents").glob("*.md")) if (plugin_dir / "agents").is_dir() else []:
        fields, body = parse_frontmatter(read_file(path))
        agents.append(AgentSource(plugin_dir.name, str(fields.get("name", path.stem)), path, fields, body))

    skills: list[SkillSource] = []
    skills_root = plugin_dir / "skills"
    for directory in sorted(path for path in skills_root.iterdir() if path.is_dir()) if skills_root.is_dir() else []:
        path = directory / "SKILL.md"
        if not path.is_file():
            continue
        fields, body = parse_frontmatter(read_file(path))
        skills.append(SkillSource(plugin_dir.name, str(fields.get("name", directory.name)), directory, fields, body))

    commands: list[CommandSource] = []
    for path in sorted((plugin_dir / "commands").glob("*.md")) if (plugin_dir / "commands").is_dir() else []:
        fields, body = parse_frontmatter(read_file(path))
        commands.append(CommandSource(plugin_dir.name, path.stem, path, fields, body))
    return agents, skills, commands


def _marketplace_entries(root: Path) -> dict[str, dict]:
    path = root / ".claude-plugin" / "marketplace.json"
    if not path.is_file():
        return {}
    return {
        str(entry.get("name", "")): entry
        for entry in read_json(path).get("plugins", [])
        if isinstance(entry, dict)
    }


def load_plugin(plugin_name: str, root: Path = WORKTREE) -> PluginSource | None:
    """Load one local plugin using the same public entry point as upstream."""
    plugin_dir = root / "plugins" / plugin_name
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    if not manifest_path.is_file():
        return None
    manifest = read_json(manifest_path)
    agents, skills, commands = _component_files(plugin_dir)
    return PluginSource(
        name=str(manifest.get("name", plugin_name)),
        dir=plugin_dir,
        plugin_json=manifest,
        agents=agents,
        skills=skills,
        commands=commands,
        marketplace_entry=_marketplace_entries(root).get(plugin_name, {}),
    )


def list_plugins(root: Path = WORKTREE) -> list[str]:
    """List source plugin directories, matching the upstream helper."""
    plugins_root = root / "plugins"
    if not plugins_root.is_dir():
        return []
    return sorted(
        path.name
        for path in plugins_root.iterdir()
        if path.is_dir() and (path / ".claude-plugin" / "plugin.json").is_file()
    )


def load_plugins(root: Path = WORKTREE) -> list[PluginSource]:
    marketplace = read_json(root / ".claude-plugin" / "marketplace.json")
    result: list[PluginSource] = []
    for entry in marketplace.get("plugins", []):
        source = entry.get("source", "")
        if not isinstance(source, str) or not source.startswith("./plugins/"):
            continue
        plugin_dir = root / source[2:]
        plugin = load_plugin(plugin_dir.name, root)
        if plugin is not None:
            plugin.marketplace_entry = entry
            result.append(plugin)
    return result


class HarnessAdapter(ABC):
    """Base class for one target harness."""

    harness_id: str = ""
    clean_paths: tuple[str, ...] = ()

    def __init__(
        self,
        root: Path | None = None,
        *,
        output_root: Path | None = None,
        source_root: Path | None = None,
        repo_root: Path | None = None,
    ):
        self.root = Path(output_root or root or WORKTREE)
        self.output_root = self.root
        self.source_root = Path(source_root or repo_root or root or WORKTREE)
        self._written: list[Path] = []

    @property
    def capabilities(self):
        from .capabilities import CAPABILITIES

        return CAPABILITIES[self.harness_id]

    def path(self, relative: str | Path) -> Path:
        path = (self.root / relative).resolve()
        root = self.root.resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"refusing to write outside output_root: {path}")
        return path

    def write(self, relative: str | Path, content: str) -> Path:
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        self._written.append(path)
        return path

    def write_bytes(self, relative: str | Path, content: bytes) -> Path:
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        self._written.append(path)
        return path

    def mirror_file(self, source: Path, relative: str | Path) -> Path:
        return self.write_bytes(relative, source.read_bytes())

    def clean(self) -> None:
        for relative in self.clean_paths:
            path = self.path(relative)
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()

    def emit_all(self, plugins: list[PluginSource], *, clean: bool = True) -> EmitResult:
        if clean:
            self.clean()
        result = EmitResult()
        for plugin in plugins:
            result.extend(self.emit_plugin(plugin))
        result.extend(self.emit_global(plugins))
        return result

    @abstractmethod
    def emit_plugin(self, plugin: PluginSource) -> EmitResult:
        raise NotImplementedError

    def emit_global(self, plugins: list[PluginSource]) -> EmitResult:
        return EmitResult()

    def strip_claude_tool_refs(self, body: str, tool_case: str = "lower") -> str:
        """Upstream-compatible wrapper around the shared tool rewriter."""
        return rewrite_tool_references(body, self.harness_id)

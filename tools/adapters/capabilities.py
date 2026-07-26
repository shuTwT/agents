"""Cross-harness capability matrix and source-to-target mappings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    harness_id: str
    display_name: str
    skills_native: bool
    agents_native: bool
    commands_native: bool
    plugin_marketplace: bool
    parallel_agents: bool
    tool_allowlist_per_agent: bool
    todowrite: bool
    task_spawn: bool
    mcp_servers: bool
    hooks: bool
    context_file_name: str | None
    context_file_max_lines: int
    skill_body_max_bytes: int
    tool_name_case: str
    bare_model_aliases: bool
    generated_paths: str
    notes: str


CAPABILITIES: dict[str, Capability] = {
    "claude-code": Capability(
        "claude-code", "Claude Code", True, True, True, True, True, True, True, True, True, True,
        "CLAUDE.md", 150, 0, "CamelCase", True, "plugins/; .claude-plugin/", "源码事实来源。",
    ),
    "codex": Capability(
        "codex", "OpenAI Codex CLI", True, True, False, False, True, False, False, False, True, False,
        "AGENTS.md", 150, 8192, "none", False, ".agents/; .codex/; plugins/*/.codex-plugin/", "Command 映射为 Skill。",
    ),
    "opencode": Capability(
        "opencode", "OpenCode", True, True, True, False, True, True, True, True, True, True,
        "AGENTS.md", 150, 0, "lowercase", False, ".opencode/; opencode.json", "使用 permission block。",
    ),
    "cursor": Capability(
        "cursor", "Cursor", True, True, True, True, True, False, False, True, True, False,
        "AGENTS.md", 150, 0, "lowercase", False, ".cursor-plugin/", "Marketplace 指向插件源码，组件复用 source。",
    ),
    "gemini": Capability(
        "gemini", "Gemini CLI", True, True, True, False, True, True, False, True, True, False,
        "AGENTS.md", 150, 0, "lowercase", False, "gemini-extension.json; agents/; skills/; commands/", "命令输出为 TOML。",
    ),
    "copilot": Capability(
        "copilot", "GitHub Copilot", True, True, False, False, False, True, False, True, True, False,
        "AGENTS.md", 150, 0, "lowercase", False, ".copilot/", "Command 映射为可手动调用 Skill。",
    ),
}


TOOL_NAME_MAPS: dict[str, dict[str, str]] = {
    "claude-code": {},
    "codex": {
        "Read": "open the file", "Edit": "edit the file", "Write": "create the file",
        "Bash": "run the shell command", "Grep": "search for the pattern", "Glob": "find matching files",
        "WebFetch": "fetch the URL", "WebSearch": "search the web", "TodoWrite": "track progress",
        "Agent": "delegate to a subagent", "Task": "delegate to a subagent",
    },
    "opencode": {
        "Read": "read", "Edit": "edit", "Write": "write", "Bash": "bash", "Grep": "grep",
        "Glob": "glob", "WebFetch": "webfetch", "WebSearch": "websearch", "TodoWrite": "todowrite",
        "Agent": "task", "Task": "task",
    },
    "cursor": {
        "Read": "read", "Edit": "edit", "Write": "write", "Bash": "run", "Grep": "search",
        "Glob": "find", "WebFetch": "fetch", "WebSearch": "web", "TodoWrite": "todo",
        "Agent": "subagent", "Task": "subagent",
    },
    "gemini": {
        "Read": "read_file", "Edit": "edit_file", "Write": "write_file", "Bash": "run_shell_command",
        "Grep": "search", "Glob": "list_files", "WebFetch": "fetch_url", "WebSearch": "google_search",
        "TodoWrite": "todo", "Agent": "@agent", "Task": "@agent",
    },
    "copilot": {
        "Read": "read", "Edit": "edit", "Write": "edit", "Bash": "execute", "Grep": "search",
        "Glob": "search", "WebFetch": "web", "WebSearch": "web", "TodoWrite": "todo",
        "Agent": "agent", "Task": "agent",
    },
}


MODEL_ALIASES: dict[str, dict[str, str]] = {
    "claude-code": {"inherit": "inherit", "opus": "opus", "sonnet": "sonnet", "haiku": "haiku"},
    "codex": {"inherit": "gpt-5.4-mini", "opus": "gpt-5.5", "sonnet": "gpt-5.4-mini", "haiku": "gpt-5.4-mini"},
    "opencode": {"inherit": "anthropic/claude-sonnet-5", "opus": "anthropic/claude-opus-4-8", "sonnet": "anthropic/claude-sonnet-5", "haiku": "anthropic/claude-haiku-4-5"},
    "cursor": {"inherit": "inherit", "opus": "inherit", "sonnet": "inherit", "haiku": "inherit"},
    "gemini": {"inherit": "gemini-2.5-pro", "opus": "gemini-2.5-pro", "sonnet": "gemini-2.5-pro", "haiku": "gemini-2.5-flash"},
    "copilot": {"inherit": "claude-sonnet-5", "opus": "claude-opus-4.8", "sonnet": "claude-sonnet-5", "haiku": "claude-haiku-4.5"},
}


def supported_harnesses() -> list[str]:
    return ["codex", "opencode", "cursor", "gemini", "copilot"]


def resolve_model(harness_id: str, source_model: str) -> tuple[str, str | None]:
    aliases = MODEL_ALIASES[harness_id]
    source_model = (source_model or "inherit").strip()
    if source_model in aliases:
        return aliases[source_model], None
    fallback = aliases["inherit"]
    return fallback, f"unknown model alias `{source_model}` for harness `{harness_id}`; falling back to `{fallback}`"

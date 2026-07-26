#!/usr/bin/env python3
"""Generate and verify all marketplace harness artifacts."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover - direct script compatibility
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools.adapters.base import load_plugins, parse_frontmatter, render_frontmatter as _render_frontmatter
    from tools.adapters.base import rewrite_tool_references as _rewrite_tool_references
    from tools.adapters.capabilities import supported_harnesses
    from tools.adapters.codex import CodexAdapter
    from tools.adapters.copilot import CopilotAdapter
    from tools.adapters.cursor import CursorAdapter
    from tools.adapters.gemini import GeminiAdapter
    from tools.adapters.opencode import OpenCodeAdapter
    from tools.docs import DOC_FILES, generate_docs, render_docs
else:
    from .adapters.base import load_plugins, parse_frontmatter, render_frontmatter as _render_frontmatter
    from .adapters.base import rewrite_tool_references as _rewrite_tool_references
    from .adapters.capabilities import supported_harnesses
    from .adapters.codex import CodexAdapter
    from .adapters.copilot import CopilotAdapter
    from .adapters.cursor import CursorAdapter
    from .adapters.gemini import GeminiAdapter
    from .adapters.opencode import OpenCodeAdapter
    from .docs import DOC_FILES, generate_docs, render_docs

ROOT = Path(__file__).resolve().parent.parent

ADAPTERS = {
    "codex": CodexAdapter,
    "opencode": OpenCodeAdapter,
    "cursor": CursorAdapter,
    "gemini": GeminiAdapter,
    "copilot": CopilotAdapter,
}

RUNTIME_ONLY_PATHS = (
    ".codex",
    ".opencode",
    "opencode.json",
    ".copilot",
    "agents",
    "skills",
    "commands",
)


def render_frontmatter(fields: dict, *, include_permission: bool = False) -> str:
    """Backward-compatible export for the phase-two frontmatter renderer."""
    return _render_frontmatter(fields, include_permission=include_permission)


def rewrite_tool_references(body: str, *, style: str) -> str:
    """Backward-compatible phase-two wrapper around the shared tool rewriter."""
    return _rewrite_tool_references(body, style)


def source_plugins(root: Path = ROOT) -> list[tuple[Path, dict]]:
    """Return the phase-two ``(plugin_dir, manifest)`` view of source plugins."""
    return [(plugin.path, plugin.plugin_json) for plugin in load_plugins(root)]


def marketplace_entries(root: Path = ROOT) -> dict[str, dict]:
    marketplace = (root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
    import json

    return {entry["name"]: entry for entry in json.loads(marketplace).get("plugins", [])}


def _selected_harnesses(harness: str) -> list[str]:
    if harness == "all":
        return supported_harnesses()
    if harness in ADAPTERS:
        return [harness]
    if harness == "none":
        return []
    raise ValueError(f"unknown harness: {harness}")


def get_adapter(
    harness_id: str,
    output_root: Path,
    *,
    source_root: Path = ROOT,
):
    """Return an adapter using the same factory contract as upstream."""
    try:
        adapter_type = ADAPTERS[harness_id]
    except KeyError as exc:
        raise ValueError(f"unknown harness: {harness_id}") from exc
    return adapter_type(output_root=output_root, source_root=source_root)


def _validate_output_root(output_root: Path) -> str | None:
    """Reject destructive generation against broad or unrelated directories."""
    resolved = output_root.resolve()
    if resolved == Path("/"):
        return "refusing to operate on the filesystem root"
    if os.environ.get("AGENTS_ALLOW_ANY_OUTPUT_ROOT") == "1":
        return None
    allowed_roots = (
        ROOT.resolve(),
        Path("/tmp").resolve(),
        Path("/private/tmp").resolve(),
        Path("/var/folders").resolve(),
        Path("/private/var/folders").resolve(),
    )
    for allowed in allowed_roots:
        if resolved == allowed or resolved.is_relative_to(allowed):
            return None
    return (
        f"refusing to clean generated paths under {resolved}; use the repository, "
        "a temporary directory, or set AGENTS_ALLOW_ANY_OUTPUT_ROOT=1"
    )


def _generate(
    root: Path,
    *,
    harness: str,
    docs: bool,
    plugin_name: str | None = None,
    output_root: Path | None = None,
    clean: bool = True,
) -> tuple[int, list[str]]:
    target_root = output_root or root
    plugins = load_plugins(root) if harness != "none" else []
    selected_plugins = plugins
    if plugin_name is not None:
        selected_plugins = [plugin for plugin in plugins if plugin.name == plugin_name]
        if not selected_plugins:
            raise ValueError(f"plugin not found: {plugin_name}")
    warnings: list[str] = []
    written_paths: set[Path] = set()
    for harness_id in _selected_harnesses(harness):
        adapter = get_adapter(harness_id, target_root, source_root=root)
        if plugin_name is None:
            result = adapter.emit_all(selected_plugins, clean=clean)
        else:
            result = adapter.emit_plugin(selected_plugins[0])
            result.extend(adapter.emit_global(plugins))
        written_paths.update(path.resolve() for path in result.written)
        warnings.extend(f"{harness_id}: {warning}" for warning in result.warnings)
    if docs:
        generate_docs(target_root, source_root=root)
        written_paths.update((target_root / relative).resolve() for relative in DOC_FILES)
    return len(written_paths), warnings


def generate(
    root: Path = ROOT,
    *,
    harness: str = "all",
    docs: bool | None = None,
    plugin_name: str | None = None,
    output_root: Path | None = None,
    clean: bool = True,
) -> int:
    if docs is None:
        docs = harness == "all"
    written, warnings = _generate(
        root,
        harness=harness,
        docs=docs,
        plugin_name=plugin_name,
        output_root=output_root,
        clean=clean and plugin_name is None,
    )
    for warning in warnings:
        print(f"[warning] {warning}")
    return written


def generate_codex(root: Path = ROOT) -> int:
    return generate(root, harness="codex", docs=False)


def generate_opencode(root: Path = ROOT) -> int:
    return generate(root, harness="opencode", docs=False)


def clean_generated(root: Path = ROOT, *, harness: str = "all", docs: bool | None = None) -> None:
    if docs is None:
        docs = harness == "all"
    for harness_id in _selected_harnesses(harness):
        get_adapter(harness_id, root, source_root=ROOT).clean()
    if docs:
        for relative in DOC_FILES:
            path = root / relative
            if path.exists():
                path.unlink()


def clean_output(harness_id: str, output_root: Path) -> int:
    """Upstream-compatible single-harness clean helper."""
    adapter = get_adapter(harness_id, output_root)
    existing = sum(adapter.path(path).exists() for path in adapter.clean_paths)
    adapter.clean()
    return existing


def prune_orphans(harness_id: str, output_root: Path, written: set[Path]) -> list[Path]:
    """Remove generated files not written by the current complete generation."""
    written_resolved = {path.resolve() for path in written}
    removed: list[Path] = []
    for relative in generated_relative_paths(output_root, harness=harness_id):
        path = (output_root / relative).resolve()
        if path not in written_resolved and path.is_file():
            path.unlink()
            removed.append(path)
    root = output_root.resolve()
    for removed_path in removed:
        directory = removed_path.parent
        while directory != root and directory.is_relative_to(root):
            try:
                directory.rmdir()
            except OSError:
                break
            directory = directory.parent
    return removed


def _add_files(root: Path, paths: set[str], directory: str) -> None:
    path = root / directory
    if path.is_dir():
        paths.update(item.relative_to(root).as_posix() for item in path.rglob("*") if item.is_file())


def generated_relative_paths(root: Path, *, harness: str = "all", docs: bool = False) -> set[str]:
    """Return every runtime artifact emitted for the selected harnesses."""
    paths: set[str] = set()
    selected = _selected_harnesses(harness)
    if "codex" in selected:
        _add_files(root, paths, ".codex")
        for relative in (".agents/plugins/marketplace.json",):
            if (root / relative).is_file():
                paths.add(relative)
        plugins_root = root / "plugins"
        if plugins_root.is_dir():
            for path in plugins_root.glob("*/.codex-plugin/plugin.json"):
                if path.is_file():
                    paths.add(path.relative_to(root).as_posix())
    if "opencode" in selected:
        _add_files(root, paths, ".opencode")
        if (root / "opencode.json").is_file():
            paths.add("opencode.json")
    if "cursor" in selected:
        _add_files(root, paths, ".cursor-plugin")
    if "gemini" in selected:
        for directory in ("agents", "skills", "commands"):
            _add_files(root, paths, directory)
        if (root / "gemini-extension.json").is_file():
            paths.add("gemini-extension.json")
    if "copilot" in selected:
        _add_files(root, paths, ".copilot")
    if docs:
        paths.update(DOC_FILES)
    return paths


def committed_generated_relative_paths(
    root: Path,
    *,
    harness: str = "all",
    docs: bool = False,
) -> set[str]:
    """Return generated files that are intentionally committed.

    Large transformed trees are local runtime artifacts and stay gitignored.
    Codex/Cursor registries, the Gemini extension manifest, and generated
    catalogs remain committed so native installation and review work from a
    fresh clone.
    """
    paths: set[str] = set()
    selected = _selected_harnesses(harness)
    if "codex" in selected:
        marketplace = ".agents/plugins/marketplace.json"
        if (root / marketplace).is_file():
            paths.add(marketplace)
        plugins_root = root / "plugins"
        if plugins_root.is_dir():
            for path in plugins_root.glob("*/.codex-plugin/plugin.json"):
                if path.is_file():
                    paths.add(path.relative_to(root).as_posix())
    if "cursor" in selected:
        _add_files(root, paths, ".cursor-plugin")
    if "gemini" in selected and (root / "gemini-extension.json").is_file():
        paths.add("gemini-extension.json")
    if docs:
        paths.update(DOC_FILES)
    return paths


def find_generated_drift(root: Path = ROOT, *, harness: str = "all", docs: bool | None = None) -> list[str]:
    """Compare only commit-worthy generated files against a fresh generation."""
    if docs is None:
        docs = harness == "all"
    with tempfile.TemporaryDirectory(prefix="agent-marketplace-check-") as temporary:
        staged = Path(temporary) / "repo"
        shutil.copytree(root, staged, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        _generate(staged, harness=harness, docs=docs)
        expected = committed_generated_relative_paths(staged, harness=harness, docs=docs)
        actual = committed_generated_relative_paths(root, harness=harness, docs=docs)
        differences: list[str] = []
        differences.extend(f"[missing] {path}" for path in sorted(expected - actual))
        differences.extend(f"[extra] {path}" for path in sorted(actual - expected))
        for relative in sorted(expected & actual):
            if (staged / relative).read_bytes() != (root / relative).read_bytes():
                differences.append(f"[changed] {relative}")
        return differences


def check_generated(root: Path = ROOT, *, harness: str = "all", docs: bool | None = None) -> int:
    differences = find_generated_drift(root, harness=harness, docs=docs)
    if differences:
        for difference in differences:
            print(difference)
        print("Committed registries or catalogs are out of date. Run `make generate-all` and commit the lightweight results.")
        return 1
    print(f"Committed generated artifacts are up to date for {harness}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", choices=(*supported_harnesses(), "all"), default="all")
    plugin_group = parser.add_mutually_exclusive_group()
    plugin_group.add_argument("--plugin", help="Generate one named plugin without cleaning other outputs.")
    plugin_group.add_argument("--all", action="store_true", help="Generate every source plugin.")
    parser.add_argument("--docs-only", action="store_true", help="Generate or check only marketplace documentation.")
    parser.add_argument("--check", action="store_true", help="Check generated files without modifying the working tree.")
    parser.add_argument("--clean", action="store_true", help="Remove selected generated artifacts and exit.")
    parser.add_argument("--prune", action="store_true", help="Prune orphan outputs; full generation already does this.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when generation emits a warning.")
    parser.add_argument("--output-root", type=Path, default=ROOT, help="Target root for generated artifacts.")
    args = parser.parse_args()
    if args.docs_only and args.harness != "all":
        parser.error("--docs-only cannot be combined with --harness")
    if args.clean and args.check:
        parser.error("--clean cannot be combined with --check")
    if args.plugin and args.clean:
        parser.error("--clean --plugin would remove outputs for other plugins")
    if args.plugin and args.prune:
        parser.error("--prune requires a complete all-plugin generation")
    if args.docs_only and (args.plugin or args.prune):
        parser.error("--docs-only cannot be combined with plugin selection or --prune")
    if args.check and args.output_root.resolve() != ROOT.resolve():
        parser.error("--check compares committed repository artifacts and cannot use --output-root")

    harness = "none" if args.docs_only else args.harness
    docs = True if args.docs_only else harness == "all"
    label = "docs" if args.docs_only else harness
    output_root = args.output_root.resolve()
    safety_error = _validate_output_root(output_root)
    if safety_error and (args.clean or not args.plugin):
        parser.error(safety_error)
    if args.clean:
        clean_generated(output_root, harness=harness, docs=docs)
        print(f"Cleaned generated artifacts for {label}.")
        if not args.all:
            return 0
    if args.check:
        return check_generated(ROOT, harness=harness, docs=docs)
    written, warnings = _generate(
        ROOT,
        harness=harness,
        docs=docs,
        plugin_name=args.plugin,
        output_root=output_root,
        clean=args.plugin is None,
    )
    for warning in warnings:
        print(f"[warning] {warning}")
    print(f"Generated {written} artifact(s) for {label}.")
    return 1 if args.strict and warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())

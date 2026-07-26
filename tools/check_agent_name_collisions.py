#!/usr/bin/env python3
"""Report duplicate Claude Code agent names across plugin source files."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

try:
    from .adapters.base import parse_frontmatter
except ImportError:  # pragma: no cover - direct script compatibility
    from adapters.base import parse_frontmatter


def find_agent_names(root: Path) -> dict[str, list[Path]]:
    by_name: dict[str, list[Path]] = defaultdict(list)
    for path in sorted((root / "plugins").glob("*/agents/*.md")):
        fields, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        name = str(fields.get("name", "")).strip()
        if name:
            by_name[name].append(path)
    return dict(by_name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--max-duplicate-names", type=int)
    parser.add_argument("--max-colliding-files", type=int)
    parser.add_argument("--fail-on-duplicates", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    duplicates = {
        name: paths
        for name, paths in find_agent_names(root).items()
        if len(paths) > 1
    }
    duplicate_count = len(duplicates)
    file_count = sum(len(paths) for paths in duplicates.values())
    if not duplicates:
        print("OK: no duplicate agent names found")
        return 0
    print(f"Found {duplicate_count} duplicate agent names across {file_count} files:")
    for name, paths in sorted(duplicates.items()):
        print(f"{name} ({len(paths)} files)")
        for path in paths:
            print(f"  - {path.relative_to(root)}")
    failed = args.fail_on_duplicates
    failed = failed or (
        args.max_duplicate_names is not None
        and duplicate_count > args.max_duplicate_names
    )
    failed = failed or (
        args.max_colliding_files is not None
        and file_count > args.max_colliding_files
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

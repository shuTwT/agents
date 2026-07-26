#!/usr/bin/env python3
"""Install generated OpenCode artifacts into the user's config directory."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_GLOBS = {"agents": "*.md", "commands": "*.md", "skills": "*"}


@dataclass
class InstallReport:
    linked: int = 0
    unchanged: int = 0
    removed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def default_config_dir(env: dict[str, str] | None = None) -> Path:
    values = env if env is not None else dict(os.environ)
    if values.get("OPENCODE_CONFIG_DIR"):
        return Path(values["OPENCODE_CONFIG_DIR"]).expanduser()
    if values.get("XDG_CONFIG_HOME"):
        return Path(values["XDG_CONFIG_HOME"]).expanduser() / "opencode"
    return Path.home() / ".config" / "opencode"


def _is_repo_link(path: Path, generated_root: Path) -> bool:
    if not path.is_symlink():
        return False
    try:
        path.resolve(strict=False).relative_to(generated_root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _artifacts(repo_root: Path) -> list[tuple[str, Path]]:
    root = repo_root / ".opencode"
    artifacts: list[tuple[str, Path]] = []
    for category, pattern in ARTIFACT_GLOBS.items():
        directory = root / category
        if not directory.is_dir():
            raise FileNotFoundError(f"{directory} is missing; generate OpenCode artifacts first")
        for source in sorted(directory.glob(pattern)):
            if category == "skills" and source.is_dir():
                artifacts.append((category, source.resolve()))
            elif category != "skills" and source.is_file():
                artifacts.append((category, source.resolve()))
    return artifacts


def _link(source: Path, destination: Path, force: bool, report: InstallReport) -> None:
    if destination.is_symlink():
        if destination.resolve(strict=False) == source:
            report.unchanged += 1
            return
        if not force:
            report.errors.append(f"{destination} points elsewhere; use --force to replace it")
            return
        destination.unlink()
    elif destination.exists():
        report.errors.append(f"{destination} is not a symlink; refusing to overwrite it")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(source, target_is_directory=source.is_dir())
    report.linked += 1


def install(*, repo_root: Path = REPO_ROOT, config_dir: Path | None = None, force: bool = False) -> InstallReport:
    report = InstallReport()
    destination_root = (config_dir or default_config_dir()).expanduser()
    try:
        artifacts = _artifacts(repo_root)
    except FileNotFoundError as exc:
        report.errors.append(str(exc))
        return report
    for category, source in artifacts:
        _link(source, destination_root / category / source.name, force, report)
    return report


def uninstall(*, repo_root: Path = REPO_ROOT, config_dir: Path | None = None) -> InstallReport:
    report = InstallReport()
    destination_root = (config_dir or default_config_dir()).expanduser()
    generated_root = repo_root / ".opencode"
    for category in ARTIFACT_GLOBS:
        directory = destination_root / category
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if _is_repo_link(path, generated_root):
                path.unlink()
                report.removed += 1
            else:
                report.skipped += 1
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    report = (
        install(repo_root=args.repo_root, config_dir=args.config_dir, force=args.force)
        if args.action == "install"
        else uninstall(repo_root=args.repo_root, config_dir=args.config_dir)
    )
    print(
        f"{args.action}: linked={report.linked} unchanged={report.unchanged} "
        f"removed={report.removed} skipped={report.skipped}"
    )
    for error in report.errors:
        print(f"error: {error}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

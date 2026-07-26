#!/usr/bin/env python3
"""Backward-compatible wrapper for tools.validate_generated."""

from __future__ import annotations

try:
    from .validate_generated import main
except ImportError:  # pragma: no cover - direct script compatibility
    from validate_generated import main


if __name__ == "__main__":
    raise SystemExit(main())

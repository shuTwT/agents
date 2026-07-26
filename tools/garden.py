#!/usr/bin/env python3
"""Backward-compatible wrapper for tools.doc_gardener."""

from __future__ import annotations

try:
    from .doc_gardener import main
except ImportError:  # pragma: no cover - direct script compatibility
    from doc_gardener import main


if __name__ == "__main__":
    raise SystemExit(main())

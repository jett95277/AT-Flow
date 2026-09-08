"""Spec orchestration (M4): decide whether a task needs the spec workflow.

Spec is an optional branch, not the main path. Heuristic signals decide;
rules are configurable. When needs_spec is true but the workflow is
unavailable, the caller must surface a clear error (no silent fallback).
"""

from __future__ import annotations

from typing import Any

# Default heuristic signals (configurable later).
_SPEC_SIGNALS = [
    "新功能", "实现", "新增", "重构整个", "大改", "新模块",
    "multi-file", "architect", "系统级", "feature",
]


def should_spec(prompt: str) -> dict[str, Any]:
    """Heuristic: does this task warrant the spec workflow?"""
    norm = prompt.lower()
    hits = [s for s in _SPEC_SIGNALS if s.lower() in norm]
    needs = bool(hits)
    return {"needs_spec": needs,
            "reason": "matched signals: " + (", ".join(hits) if hits else "none"),
            "scale": "large" if needs else "light"}

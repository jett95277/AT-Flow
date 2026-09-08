"""Skill orchestration (M4): route domain skills from a task prompt.

Scans installed domain skills (SKILL.md description) and returns matching
skill hints so the orchestration guidance can carry "how to do it" pointers.
Empty match is fine (base path); a skill is guidance, never an executor.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


def _find_skills_dir() -> Path | None:
    """Locate the domain skills directory: env > ~/.xiaot/skills > package repo."""
    env = os.environ.get("XIAOT_SKILLS")
    if env and Path(env).exists():
        return Path(env)
    home = Path.home() / ".xiaot" / "skills"
    if home.exists():
        return home
    # package location: lib/python/xiaot/ -> repo root/skills
    repo = Path(__file__).resolve().parents[3]
    candidate = repo / "skills"
    return candidate if candidate.exists() else None


def _read_description(skill_dir: Path) -> str:
    md = skill_dir / "SKILL.md"
    if not md.exists():
        return ""
    try:
        text = md.read_text(encoding="utf-8")
    except Exception:
        return ""
    m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _trigger_terms(description: str) -> list[str]:
    """Extract trigger phrases: '中文触发：a / b / c' or quoted groups."""
    terms: list[str] = []
    m = re.search(r"中文触发[:：]\s*([^。\n]+)", description)
    if m:
        terms = [t.strip() for t in re.split(r"[、/,，]", m.group(1)) if t.strip()]
    if not terms:  # fall back to short quoted phrases
        terms = [t.strip('"\'') for t in re.findall(r'[""]([^""]{1,20})[""]', description)]
    return terms


def resolve(prompt: str, limit: int = 3) -> list[dict[str, Any]]:
    """Return matching skill hints for a task prompt."""
    skills_dir = _find_skills_dir()
    if not skills_dir:
        return []
    prompt_norm = prompt.lower()
    hints: list[dict[str, Any]] = []
    for d in sorted(skills_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        desc = _read_description(d)
        if not desc:
            continue
        terms = _trigger_terms(desc)
        matched = []
        for t in terms:
            if not t:
                continue
            tl = t.lower()
            if tl in prompt_norm or (len(t) >= 2 and t[:2].lower() in prompt_norm):
                matched.append(t)
        if matched:
            hints.append({"name": d.name, "matched": matched,
                          "description": desc[:100]})
            if len(hints) >= limit:
                break
    return hints

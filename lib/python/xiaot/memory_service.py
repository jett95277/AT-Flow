"""Memory orchestration service (M2): thin wrapper over xiaot_memory, A model.

A model: memory = cross-session verified knowledge. Only medium{task,project}
and long{global} are retrieved/injected; short process entries are excluded.
In-flight state lives in workspace. Settling produces comparison suggestions
(duplicate/review with scope hints) for human approval - nothing auto-promotes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _load_memory_ctx(root: Path, uris: list[str]) -> dict[str, Any]:
    """Load injectable memory context for candidate URIs via existing engine."""
    from xiaot_memory import memory_context as mc

    injectable = mc.injectable_uris(root, uris) if uris else []
    ctx = mc.build_memory_context(root, injectable) if injectable else {}
    return ctx if isinstance(ctx, dict) else {}


def candidate_uris(task: dict[str, Any]) -> list[str]:
    """A-model candidate URIs: medium{task,project} + long{global}.

    short/session is deliberately excluded (process state lives in workspace).
    """
    uris: list[str] = []
    project = task.get("project")
    task_id = task.get("id", "")
    if task_id.startswith("task-"):
        topic = task_id[len("task-"):]
        uris.append(f"memory://task/{topic}/medium")
    if project:
        uris.append(f"memory://project/{project}/medium")
        uris.append(f"memory://project/{project}/long")
    # cross-project stable knowledge lives in global scope (long)
    uris.append("memory://global/knowledge/long")
    return uris


def retrieve(root: Path, task: dict[str, Any], budget: int = 5) -> dict[str, Any]:
    """Inject A-model memory as inline summary + reference info.

    Returns:
      present  - whether any memory was found
      summary  - inline entries (bounded by budget)
      uris     - candidate uris probed
      refs     - {"total", "inline", "uris"} for over-budget read-by-reference
    """
    uris = candidate_uris(task)
    ctx = _load_memory_ctx(root, uris)
    entries_map = ctx.get("entries", {}) if isinstance(ctx, dict) else {}
    if not isinstance(entries_map, dict):
        entries_map = {}
    total = 0
    summary: list[dict[str, Any]] = []
    for uri, entries in entries_map.items():
        for e in entries if isinstance(entries, list) else []:
            if not isinstance(e, dict):
                continue
            total += 1
            if len(summary) < budget:
                summary.append({
                    "uri": e.get("uri") or uri,
                    "summary": str(e.get("content", ""))[:120],
                })
    return {
        "present": total > 0,
        "summary": summary,
        "uris": uris,
        "refs": {"total": total, "inline": len(summary), "uris": list(entries_map.keys())},
    }


def _existing_task_contents(root: Path) -> list[dict[str, Any]]:
    """Read every medium task-scope entry content (for settle comparison)."""
    entries: list[dict[str, Any]] = []
    d = root / ".agent" / "memory" / "medium"
    if not d.exists():
        return entries
    for path in sorted(d.glob("task-*.md")):
        for e in read_all_entries(path):
            entries.append(e)
    return entries


def read_all_entries(path: Path) -> list[dict[str, Any]]:
    import yaml
    try:
        text = path.read_text(encoding="utf-8")
        return [e for e in yaml.safe_load_all(text) if isinstance(e, dict)]
    except Exception:
        return []


def _norm(text: str) -> str:
    return "".join(str(text).split())


def compare_candidates(root: Path, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compare settle candidates against existing medium task memory.

    Each suggestion: {text, action: duplicate|review, existing_uri?, scope}.
    scope hint comes from the candidate (project-level facts -> project scope,
    topic conclusions -> task scope); the human decides in the end.
    Nothing auto-writes.
    """
    existing = _existing_task_contents(root)
    existing_norm = {_norm(e.get("content", "")): e.get("uri", "") for e in existing}
    suggestions: list[dict[str, Any]] = []
    for cand in candidates:
        text = str(cand.get("text", ""))
        scope = cand.get("scope") if cand.get("scope") in ("task", "project") else "task"
        if _norm(text) in existing_norm and text:
            suggestions.append({
                "text": text[:120],
                "action": "duplicate",
                "existing_uri": existing_norm[_norm(text)],
                "scope": scope,
                "reason": "same conclusion already stored",
            })
        else:
            suggestions.append({
                "text": text[:120],
                "action": "review",
                "existing_uri": None,
                "scope": scope,
                "reason": ("project-level fact -> project scope" if scope == "project"
                           else "topic conclusion -> task scope"),
            })
    return suggestions


def confirm(root: Path, text: str, scope: str = "task",
            project: str | None = None, task_id: str | None = None,
            evidence: str | None = None) -> dict[str, Any]:
    """Human-approved promotion into medium memory (manual gate).

    A-model: nothing auto-promotes. After the human approves a settle
    suggestion this writes a verified-style entry to the chosen scope
    (task topic or project). Default MemoryService implementation.

    task scope: `task_id` may be the full workspace id ("task-<topic>") or a
    bare topic; the memory URI always uses the bare topic so retrieval
    (candidate_uris) and writes share one namespace (file task-<topic>.md).
    """
    if scope not in ("task", "project"):
        return {"ok": False, "error": "scope must be task or project"}
    if scope == "task" and not task_id:
        return {"ok": False, "error": "task scope needs task_id (topic)"}
    if scope == "project" and not project:
        return {"ok": False, "error": "project scope needs project"}
    from xiaot_memory.memory import write_memory_structured

    if scope == "task":
        topic = task_id[len("task-"):] if str(task_id).startswith("task-") else task_id
        if not topic:
            return {"ok": False, "error": "task scope needs a non-empty topic"}
        uri = f"memory://task/{topic}/medium"
    else:
        uri = f"memory://project/{project}/medium"
    source = {"project": project} if scope == "project" else {}
    if evidence:
        source["evidence"] = evidence
    if task_id:
        source["task"] = task_id
    item = write_memory_structured(root, uri, conclusion=text, source=source)
    return {"ok": True, "uri": uri, "scope": scope, "content": text[:120],
            "item": item}


def suggest_settle(root: Path, task_id: str,
                   candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """End-of-task settle: compare candidates against memory, human confirms all."""
    from xiaot import workspace

    cands = candidates or []
    if not cands:
        w = workspace.xiaot_root(root) / "workspace" / task_id
        if (w / "result.md").exists():
            cands = [{"text": f"task {task_id} outcome; review result.md", "source": task_id}]
    return {
        "task_id": task_id,
        "suggestions": compare_candidates(root, cands),
        "policy": "all_promotions_manual",
    }

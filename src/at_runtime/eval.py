from __future__ import annotations

from pathlib import Path
from typing import Any

from at_runtime.context import estimate_tokens
from at_runtime.execution import LocalAdapter, build_prompt
from at_runtime.observer import list_events
from at_runtime.runner import run_task_flow


def run_minimal_eval(root: Path, demo_task: str, provider: str = "mock") -> dict:
    if provider == "mock":
        baseline_text = f"baseline done: {demo_task}"
        baseline_success = True
    else:
        baseline_bundle = {
            "task": {"id": "BASELINE", "goal": demo_task},
            "role": {"type": "baseline"},
            "constraints": [],
            "handoff": {"from": None, "summary": ""},
            "relevant_memory": [],
            "knowledge": [],
        }
        baseline_text = build_prompt(baseline_bundle, "baseline")
        try:
            LocalAdapter().spawn(baseline_bundle, "baseline", root)
            baseline_success = True
        except Exception:
            baseline_success = False
    baseline_tokens = estimate_tokens(baseline_text)
    steps = run_task_flow(
        root,
        "EVAL1",
        demo_task,
        {"constraints": []},
        provider=provider,
    )
    injected = [
        event
        for event in list_events(root)
        if event["event"] == "context.injected"
    ]
    at_tokens = sum(event["data"].get("tokens", 0) for event in injected)
    sufficiency = all(step["status"] == "done" for step in steps)
    return {
        "baseline": {
            "task_success": baseline_success,
            "estimated_tokens": baseline_tokens,
        },
        "at_flow": {
            "task_success": sufficiency,
            "estimated_tokens": at_tokens,
            "handoff_sufficiency": sufficiency,
            "sessions": len(steps),
        },
    }

# AT V1.8 Codex Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AT Flow explicitly detect and surface Codex provider capability so the system does not pretend a GPT/OpenAI API call is equivalent to mature Codex code-agent execution.

**Architecture:** Provider availability is checked by the AT runtime without executing arbitrary agent work. The FastAPI doctor endpoint exposes provider capability checks, and the Web Console displays them as runtime diagnostics. Codex remains a process provider behind AT's state, artifact, trace, audit, and permission contracts.

**Tech Stack:** Python standard library, FastAPI, React, TypeScript, unittest, Vitest.

## Global Constraints

- V1.8 owns Codex capability visibility and failure clarity.
- V1.8 must not implement opencode as the primary extension target.
- OpenAI/GPT API may support translation or lightweight tasks, but must not be presented as Codex-equivalent code-agent execution.
- Provider checks must not run full agent tasks.
- Provider checks must not mutate `.at` runtime data.
- No secrets may be read, written, logged, or committed.
- Every code task must add a failing test before implementation.

---

## Task 1: Provider Capability Check

**Files:**
- Modify: `src/at_flow/providers.py`
- Create: `tests/test_provider_capabilities.py`

**Interfaces:**
- Produces: `check_provider_capability(name: str, config: dict[str, Any]) -> dict[str, Any]`
- Output keys: `name`, `available`, `provider_type`, `detail`

Checks:
- `mock`: available.
- known `process` provider with command on PATH: available.
- known `process` provider with missing command: unavailable.
- unknown provider: unavailable.

## Task 2: Doctor Includes Provider Checks

**Files:**
- Modify: `src/at_flow/inspectors.py`
- Test: `tests/test_web_api.py`

**Interfaces:**
- Consumes: `check_provider_capability(name, config)`
- Produces doctor check rows named `provider:<name>`.

## Task 3: Web Console Shows Doctor Checks

**Files:**
- Modify: `web/src/api/types.ts`
- Modify: `web/src/components/AppShell.tsx`
- Modify: `web/src/components/RuntimeEvidence.tsx`
- Modify: `web/src/components/RuntimeEvidence.test.tsx`

**Interfaces:**
- RuntimeEvidence accepts `doctor: DoctorCheck[]`.
- Refresh Doctor stores and displays provider checks.

## Task 4: V1.8 Verification

Run:

```powershell
python -m unittest discover -s tests
cd web
npm.cmd test -- --run
npm.cmd run build
```

If Windows sandbox blocks `web/dist`, rerun build with explicit elevated approval and record the reason.

## Completion

Commit after verification:

```powershell
git add docs/superpowers/plans/2026-08-02-at-v1-8-codex-capability-implementation-plan.md src/at_flow/providers.py src/at_flow/inspectors.py tests/test_provider_capabilities.py tests/test_web_api.py web/src/api/types.ts web/src/components/AppShell.tsx web/src/components/RuntimeEvidence.tsx web/src/components/RuntimeEvidence.test.tsx
git commit -m "feat: add v1.8 codex capability checks"
```

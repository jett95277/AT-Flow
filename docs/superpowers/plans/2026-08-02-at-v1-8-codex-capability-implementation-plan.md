# AT V1.8 Codex Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AT Flow explicitly detect and surface Codex provider capability,
then complete the V1.8 language path without pretending that a GPT/OpenAI API
call is equivalent to mature Codex code-agent execution.

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

## Corrective Remediation

The original V1.8 scope only proved executable discovery and diagnostics. It did
not implement the promised Chinese-input/English-runtime/Chinese-display flow,
and the canonical Agent packages still appeared under the shared area.

The corrective plan is tracked separately in:

```text
docs/superpowers/plans/2026-08-02-at-v1-8-language-and-agent-layout-remediation-plan.md
```

That remediation owns:

- canonical Agent packages under `.at/agents`;
- explicit migration from the legacy `.at/shared/agents` layout;
- Language Contract V2 and a restricted translation provider boundary;
- English-only runtime prompts, contexts, artifacts, and handoffs;
- Chinese display artifacts and visible no-fallback failure states;
- Web Console language status and structured artifact APIs.

## Completion

V1.8 is complete only after both this capability plan and the corrective
remediation plan pass their full verification. Git operations are handled in a
separate development window.

# AT Ultimate Runtime Development Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the final AT Flow runtime by combining AT's existing multi-agent isolation with Baize-inspired topic memory, timeline continuity, SOP routing, persona overlays, human-friendly startup interaction, and one-time approval guards.

**Architecture:** AT remains a Python standard-library runtime. The runtime owns state transitions, topic registry, timeline, session archive, SOP routing, persona selection, context construction, handoff routing, memory proposal review, audit, approval, retry, provider checks, and ASCII rendering. Providers execute only one bounded agent step using explicit paths from `context.json`.

**Tech Stack:** Python standard library, `unittest`, JSON contracts, Markdown memory files, PowerShell-friendly CLI, ASCII chat rendering.

## Single Source Of Truth

This file is the single implementation plan for AT Flow after absorbing the Baize system design.

Primary design input:

- `docs/superpowers/specs/2026-07-31-baize-at-integration-design.md`

Supporting engineering principles:

- `docs/developing-at.md`
- `docs/runtime-contracts.md`
- `docs/architecture.md`

## Global Constraints

- Keep external dependencies at zero unless a later approved plan explicitly adds one.
- Use TDD for every behavior change: write the failing test, run it, implement the smallest code, then rerun.
- Run `python -m unittest discover -s tests` as the baseline verification command.
- Run `python -m compileall src tests at.py` before claiming code is complete.
- Keep the default agent pipeline order: `main -> analysis -> code -> test`.
- Do not expose `AT_WORKSPACE_ROOT`, `AT_SHARED_ROOT`, or `AT_SESSION_DIR` in the default process provider environment.
- Do not let agents directly write `.at/shared/memory`, `.at/shared/skills`, `.at/shared/policies`, other agent directories, `state.json`, or `handoff`.
- Do not let persona or SOP files override `permissions.json`.
- Do not import damaged Baize markdown files directly.
- Do not depend on Baize's SQLite database.
- Do not introduce Bash as a required runtime dependency.
- Do not add automatic commit or push.
- Treat ASCII/TUI output as presentation. Runtime contracts, recovery, artifacts, audit, approvals, and tests have higher priority.
- This workspace currently has no `.git` directory, so each task ends with a verification checkpoint instead of a git commit.

---

## Development Nodes

1. State lifecycle and recovery
2. Topic runtime
3. Timeline and session archive
4. Context selection contract v2
5. SOP routing
6. Persona overlay
7. Memory proposal review and apply flow
8. Artifact validation and handoff contract
9. Observability commands
10. Retry, abort, and reroute controls
11. Approval guard
12. Provider capability checks
13. End-to-end scenario suite
14. Conversation ASCII polish

---

### Task 1: State Lifecycle And Recovery

**Files:**
- Modify: `src/at_flow/models.py`
- Modify: `src/at_flow/transitions.py`
- Modify: `src/at_flow/engine.py`
- Test: `tests/test_runtime_contracts.py`
- Docs: `docs/runtime-contracts.md`

**Interfaces:**
- Consumes: `SessionState`, `StepState`, `transition_step()`, `retry_failed_step()`
- Produces: `recover_interrupted_step(session: SessionState, step_index: int, reason: str) -> None`
- Produces: `SessionState.interrupted_steps() -> list[int]`

- [ ] **Step 1: Write the failing recovery test**

Add this test to `tests/test_runtime_contracts.py`:

```python
def test_running_step_can_be_marked_failed_during_recovery(self) -> None:
    session = SessionState.new(
        task="recover running",
        project_path=Path("project"),
        provider="mock",
        pipeline=["main"],
    )
    transition_step(session, 0, "running")

    recover_interrupted_step(session, 0, "stale lock recovered")

    self.assertEqual(session.steps[0].status, "failed")
    self.assertIn("stale lock recovered", session.steps[0].failure_reason or "")
    self.assertTrue(session.steps[0].retryable)
    self.assertEqual(session.status, "failed")
```

- [ ] **Step 2: Verify the test fails**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_runtime_contracts.RuntimeContractsTests.test_running_step_can_be_marked_failed_during_recovery
```

Expected:

```text
NameError: name 'recover_interrupted_step' is not defined
```

- [ ] **Step 3: Implement recovery helpers**

In `src/at_flow/models.py`, add:

```python
def interrupted_steps(self) -> list[int]:
    return [index for index, step in enumerate(self.steps) if step.status == "running"]
```

In `src/at_flow/transitions.py`, add:

```python
def recover_interrupted_step(session: SessionState, step_index: int, reason: str) -> None:
    step = session.steps[step_index]
    if step.status != "running":
        raise TransitionError(f"Cannot recover non-running step: {step.status}")
    transition_step(session, step_index, "failed", error=reason, retryable=True)
```

- [ ] **Step 4: Wire recovery into `Runner.run()`**

After loading a session, if `session.interrupted_steps()` returns indexes, recover the first running step, trace `recover_interrupted_step`, save the session, and stop so the user can choose retry.

- [ ] **Step 5: Verify Task 1**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_runtime_contracts
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

### Task 2: Topic Runtime

**Files:**
- Create: `src/at_flow/topics.py`
- Modify: `src/at_flow/workspace.py`
- Modify: `src/at_flow/cli.py`
- Test: `tests/test_topics.py`
- Docs: `docs/runtime-contracts.md`
- Docs: `README.md`

**Interfaces:**
- Produces: `TopicRecord`
- Produces: `load_topic_index(workspace: ATWorkspace) -> TopicIndex`
- Produces: `create_topic(workspace: ATWorkspace, name: str) -> TopicRecord`
- Produces: `switch_topic(workspace: ATWorkspace, query: str) -> TopicRecord`
- Produces: `active_topic(workspace: ATWorkspace) -> TopicRecord | None`
- Produces: CLI commands `topic list`, `topic create`, `topic switch`, `topic status`

- [ ] **Step 1: Write failing topic tests**

Create `tests/test_topics.py`:

```python
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.topics import active_topic, create_topic, load_topic_index, switch_topic
from at_flow.workspace import ATWorkspace


class TopicRuntimeTests(unittest.TestCase):
    def test_create_topic_writes_topic_files_and_sets_active_topic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            topic = create_topic(workspace, "AT Runtime")

            self.assertEqual(topic.name, "AT Runtime")
            self.assertEqual(active_topic(workspace).id, topic.id)
            topic_dir = workspace.topics_root / topic.id
            self.assertTrue((topic_dir / "topic.json").exists())
            self.assertTrue((topic_dir / "context.md").exists())
            self.assertTrue((topic_dir / "context_summary.md").exists())
            self.assertTrue((topic_dir / "timeline.md").exists())
            self.assertTrue((topic_dir / "sessions").is_dir())
            self.assertTrue((topic_dir / "artifacts").is_dir())
            self.assertTrue((topic_dir / "references").is_dir())

    def test_switch_topic_by_name_updates_active_topic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            create_topic(workspace, "AT Runtime")
            second = create_topic(workspace, "Baize Integration")

            selected = switch_topic(workspace, "Baize")

            self.assertEqual(selected.id, second.id)
            self.assertEqual(load_topic_index(workspace).active_topic, second.id)
```

- [ ] **Step 2: Verify the tests fail**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_topics
```

Expected:

```text
ModuleNotFoundError: No module named 'at_flow.topics'
```

- [ ] **Step 3: Implement topic paths**

In `src/at_flow/workspace.py`, add:

```python
@property
def topics_root(self) -> Path:
    return self.root / ".at" / "topics"

def topic_index_path(self) -> Path:
    return self.topics_root / "index.json"
```

Ensure `topics_root` is created by `ensure_layout()`.

- [ ] **Step 4: Implement `src/at_flow/topics.py`**

Create dataclasses:

```python
@dataclass
class TopicRecord:
    id: str
    name: str
    path: str
    status: str
    created_at: str
    last_active: str
    summary: str

@dataclass
class TopicIndex:
    schema_version: int
    active_topic: str | None
    topics: list[TopicRecord]
```

Implement JSON load/save, slug generation from topic name, topic directory creation, and active topic update.

- [ ] **Step 5: Add CLI topic commands**

Add subcommands:

```text
topic list
topic create <name>
topic switch <id-or-name>
topic status
```

Output must be plain text and usable in Codex conversation mode.

- [ ] **Step 6: Verify Task 2**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_topics
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

### Task 3: Timeline And Session Archive

**Files:**
- Create: `src/at_flow/timeline.py`
- Modify: `src/at_flow/topics.py`
- Modify: `src/at_flow/cli.py`
- Modify: `src/at_flow/render.py`
- Test: `tests/test_timeline.py`
- Docs: `docs/runtime-contracts.md`
- Docs: `README.md`

**Interfaces:**
- Produces: `append_timeline_event(workspace: ATWorkspace, topic_id: str, kind: str, ref: str, message: str) -> Path`
- Produces: `read_timeline(workspace: ATWorkspace, topic_id: str, limit: int = 5) -> list[str]`
- Produces: `save_session_archive(workspace: ATWorkspace, session_id: str, topic_id: str | None = None) -> Path`
- Produces: CLI commands `topic timeline`, `save-session`

- [ ] **Step 1: Write failing timeline tests**

Create `tests/test_timeline.py`:

```python
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.models import SessionState
from at_flow.timeline import append_timeline_event, read_timeline, save_session_archive
from at_flow.topics import create_topic
from at_flow.workspace import ATWorkspace


class TimelineTests(unittest.TestCase):
    def test_append_and_read_timeline_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            topic = create_topic(workspace, "AT Runtime")

            append_timeline_event(workspace, topic.id, "decision", "topic-runtime", "Use topic memory.")

            entries = read_timeline(workspace, topic.id)
            self.assertEqual(len(entries), 1)
            self.assertIn("decision", entries[0])
            self.assertIn("Use topic memory.", entries[0])

    def test_save_session_archive_writes_topic_session_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            topic = create_topic(workspace, "AT Runtime")
            session = SessionState.new("archive me", workspace.projects_root / "demo", "mock", pipeline=["main"])
            workspace.create_session(session)

            archive = save_session_archive(workspace, session.id, topic.id)

            self.assertTrue(archive.exists())
            self.assertEqual(archive.parent.name, "sessions")
            self.assertIn("archive me", archive.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Verify the tests fail**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_timeline
```

Expected:

```text
ModuleNotFoundError: No module named 'at_flow.timeline'
```

- [ ] **Step 3: Implement timeline append/read**

Timeline lines must use:

```text
YYYY-MM-DD HH:MM | <kind> | <ref> | <message>
```

Use `now_iso()` for time source and format a readable local prefix from it.

- [ ] **Step 4: Implement session archive**

Archive file:

```text
.at/topics/<topic-id>/sessions/<session-id>.md
```

Archive sections:

```text
# AT Session Archive

session:
topic:
task:
status:
provider:

## Steps
## Artifacts
## Failures
## Next
```

- [ ] **Step 5: Add CLI commands and startup panel data**

Add:

```text
topic timeline <id-or-name>
save-session <session-id>
```

`panel --format chat` should include active topic and recent timeline after the AT state machine.

- [ ] **Step 6: Verify Task 3**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_timeline
$env:PYTHONPATH='src'; python -m unittest tests.test_render
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

### Task 4: Context Selection Contract V2

**Files:**
- Modify: `src/at_flow/context_contracts.py`
- Modify: `src/at_flow/providers.py`
- Modify: `src/at_flow/topics.py`
- Test: `tests/test_context_memory_contracts.py`
- Test: `tests/test_topics.py`
- Docs: `docs/runtime-contracts.md`

**Interfaces:**
- Consumes: `build_agent_context_contract(context: AgentContext) -> dict[str, Any]`
- Produces: `list_authorized_shared_files(shared_root: Path, permissions: dict[str, Any]) -> dict[str, list[str]]`
- Produces: context JSON keys `selected_files`, `topic`, `sop`, `persona`

- [ ] **Step 1: Write failing context v2 test**

Add to `tests/test_context_memory_contracts.py`:

```python
def test_context_contract_lists_selected_files_topic_and_no_roots(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        workspace = ATWorkspace.init(Path(directory))
        topic = create_topic(workspace, "AT Runtime")
        session = SessionState.new("context v2", workspace.projects_root / "demo", "mock", pipeline=["main"])
        workspace.create_session(session)

        result = Runner(workspace).run(session.id, one_step=True)

        self.assertTrue(result.is_complete())
        context = json.loads(workspace.session_context_path(session.id, "main").read_text(encoding="utf-8"))
        self.assertIn("selected_files", context)
        self.assertIn("topic", context)
        self.assertEqual(context["topic"]["id"], topic.id)
        self.assertNotIn("shared_root", json.dumps(context))
        self.assertNotIn("session_dir", json.dumps(context))
        self.assertNotIn("workspace_root", json.dumps(context))
```

- [ ] **Step 2: Verify the test fails**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_context_memory_contracts.ContextMemoryContractTests.test_context_contract_lists_selected_files_topic_and_no_roots
```

Expected:

```text
AssertionError: 'selected_files' not found
```

- [ ] **Step 3: Implement selected file listing**

Add to `src/at_flow/context_contracts.py`:

```python
def list_authorized_shared_files(shared_root: Path, permissions: dict[str, Any]) -> dict[str, list[str]]:
    read = permissions.get("read", {})
    selected = {"memory": [], "skills": [], "policies": [], "docs": []}
    if read.get("shared_memory"):
        selected["memory"] = _list_files(shared_root / "memory")
    if read.get("shared_skills"):
        selected["skills"] = _list_files(shared_root / "skills")
    if read.get("shared_policies"):
        selected["policies"] = _list_files(shared_root / "policies")
    if read.get("shared_docs"):
        selected["docs"] = _list_files(shared_root / "docs")
    return selected
```

- [ ] **Step 4: Add topic/persona/SOP placeholders to context**

Context must include:

```json
{
  "topic": {"id": "...", "name": "...", "summary_path": "...", "timeline_path": "..."},
  "persona": null,
  "sop": null
}
```

Use `null` when not selected. Do not expose full topic root.

- [ ] **Step 5: Verify Task 4**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_context_memory_contracts
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

### Task 5: SOP Routing

**Files:**
- Create: `src/at_flow/sop.py`
- Modify: `src/at_flow/workspace.py`
- Modify: `src/at_flow/context_contracts.py`
- Modify: `src/at_flow/cli.py`
- Test: `tests/test_sop.py`
- Docs: `docs/runtime-contracts.md`
- Docs: `README.md`

**Interfaces:**
- Produces: `SOPRoute`
- Produces: `load_sop_routes(workspace: ATWorkspace) -> list[SOPRoute]`
- Produces: `match_sop(workspace: ATWorkspace, text: str) -> list[SOPRoute]`
- Produces: CLI command `sop match <text>`

- [ ] **Step 1: Write failing SOP route tests**

Create `tests/test_sop.py`:

```python
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.sop import load_sop_routes, match_sop
from at_flow.workspace import ATWorkspace


class SOPRoutingTests(unittest.TestCase):
    def test_default_sop_routes_are_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            routes = load_sop_routes(workspace)

            self.assertIn("save-session", [route.name for route in routes])
            self.assertTrue((workspace.shared_root / "sop" / "save-session.md").exists())

    def test_match_sop_by_keyword(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            matches = match_sop(workspace, "保存当前会话")

            self.assertEqual([item.name for item in matches], ["save-session"])
```

- [ ] **Step 2: Verify the tests fail**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_sop
```

Expected:

```text
ModuleNotFoundError: No module named 'at_flow.sop'
```

- [ ] **Step 3: Initialize SOP directory**

`ensure_layout()` must create:

```text
.at/shared/sop/
  routing.json
  create-topic.md
  switch-topic.md
  save-session.md
  prd.md
  tech-design.md
  code-review.md
  bugfix.md
```

- [ ] **Step 4: Implement route matching**

`routing.json` schema:

```json
{
  "schema_version": 1,
  "routes": [
    {"name": "save-session", "keywords": ["保存", "save", "归档"], "path": "save-session.md"}
  ]
}
```

Matching is case-insensitive for ASCII and direct substring match for Chinese.

- [ ] **Step 5: Add SOP route into context**

When a session starts with a selected SOP, `context.json` must include:

```json
"sop": {"name": "save-session", "path": ".../.at/shared/sop/save-session.md"}
```

- [ ] **Step 6: Verify Task 5**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_sop
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

### Task 6: Persona Overlay

**Files:**
- Create: `src/at_flow/personas.py`
- Modify: `src/at_flow/workspace.py`
- Modify: `src/at_flow/context_contracts.py`
- Modify: `src/at_flow/providers.py`
- Test: `tests/test_personas.py`
- Docs: `docs/runtime-contracts.md`

**Interfaces:**
- Produces: `PersonaRecord`
- Produces: `load_persona(workspace: ATWorkspace, name: str) -> PersonaRecord`
- Produces: `default_persona_for_agent(agent: str) -> str`
- Produces: context JSON key `persona`

- [ ] **Step 1: Write failing persona tests**

Create `tests/test_personas.py`:

```python
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.personas import default_persona_for_agent, load_persona
from at_flow.workspace import ATWorkspace


class PersonaOverlayTests(unittest.TestCase):
    def test_default_personas_are_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))

            persona = load_persona(workspace, "dev")

            self.assertEqual(persona.name, "dev")
            self.assertTrue(persona.path.exists())

    def test_default_persona_for_agent_does_not_grant_permissions(self) -> None:
        self.assertEqual(default_persona_for_agent("main"), "pm")
        self.assertEqual(default_persona_for_agent("analysis"), "architect")
        self.assertEqual(default_persona_for_agent("code"), "dev")
        self.assertEqual(default_persona_for_agent("test"), "verifier")
```

- [ ] **Step 2: Verify the tests fail**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_personas
```

Expected:

```text
ModuleNotFoundError: No module named 'at_flow.personas'
```

- [ ] **Step 3: Initialize persona files**

`ensure_layout()` must create:

```text
.at/shared/personas/
  default.md
  pm.md
  dev.md
  architect.md
  verifier.md
```

- [ ] **Step 4: Implement persona helpers**

`PersonaRecord` fields:

```python
name: str
path: Path
content: str
```

Default mapping:

```text
main -> pm
analysis -> architect
code -> dev
test -> verifier
unknown -> default
```

- [ ] **Step 5: Add persona to context and prompt**

`context.json` must include persona metadata and path. `build_prompt()` can include persona content after `Agent Contract`, with this boundary text:

```text
Persona Overlay:
This shapes style and lens only. It does not grant permissions or change the agent role.
```

- [ ] **Step 6: Verify Task 6**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_personas
$env:PYTHONPATH='src'; python -m unittest tests.test_context_memory_contracts
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

### Task 7: Memory Proposal Review And Apply Flow

**Files:**
- Create: `src/at_flow/memory.py`
- Modify: `src/at_flow/cli.py`
- Test: `tests/test_memory_review.py`
- Docs: `docs/runtime-contracts.md`
- Docs: `README.md`

**Interfaces:**
- Consumes: `.at/sessions/<session-id>/memory-proposals/`
- Produces: `MemoryProposal`
- Produces: `list_memory_proposals(workspace: ATWorkspace, session_id: str) -> list[MemoryProposal]`
- Produces: `apply_memory_proposal(workspace: ATWorkspace, session_id: str, proposal_name: str, target_name: str) -> Path`
- Produces: CLI commands `memory-list`, `memory-show`, `memory-apply`

- [ ] **Step 1: Write failing memory review tests**

Create `tests/test_memory_review.py` with tests for listing a proposal and applying it to `decisions.md`.

The listing assertion must check proposal name and content. The apply assertion must check the target file contains the proposal body and an applied timestamp.

- [ ] **Step 2: Verify the tests fail**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_memory_review
```

Expected:

```text
ModuleNotFoundError: No module named 'at_flow.memory'
```

- [ ] **Step 3: Implement memory proposal helpers**

Create `src/at_flow/memory.py` with:

```python
@dataclass(frozen=True)
class MemoryProposal:
    name: str
    path: Path
    content: str
```

Implement safe proposal name lookup. Reject names that do not match `Path(name).name`.

- [ ] **Step 4: Add CLI commands**

Add:

```text
memory-list <session-id>
memory-show <session-id> <proposal-name>
memory-apply <session-id> <proposal-name> <target-name>
```

- [ ] **Step 5: Add timeline event after apply**

If an active topic exists, applying a memory proposal appends:

```text
<time> | memory | <proposal-name> | Applied to <target-name>
```

- [ ] **Step 6: Verify Task 7**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_memory_review
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

### Task 8: Artifact Validation And Handoff Contract

**Files:**
- Create: `src/at_flow/artifacts.py`
- Modify: `src/at_flow/engine.py`
- Test: `tests/test_artifact_contracts.py`
- Docs: `docs/runtime-contracts.md`

**Interfaces:**
- Consumes: `outbox/artifact.md`, `output.md`
- Produces: `validate_artifact_contract(agent: str, output_contract: str, artifact: str) -> list[str]`
- Produces: trace event `artifact_contract_failed`

- [ ] **Step 1: Write failing artifact test**

Create `tests/test_artifact_contracts.py` with a test where `output.md` requires:

```text
- Changed Files
- Behavioral Changes
- Verification Suggestions
```

The artifact contains only `## Changed Files`. Expected missing sections:

```python
["Behavioral Changes", "Verification Suggestions"]
```

- [ ] **Step 2: Verify the test fails**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_artifact_contracts
```

Expected:

```text
ModuleNotFoundError: No module named 'at_flow.artifacts'
```

- [ ] **Step 3: Implement artifact validator**

Create `src/at_flow/artifacts.py`. Parse required sections from bullet lines in `output.md`. Parse present sections from markdown headings in artifact content.

- [ ] **Step 4: Wire validation into runner**

After `_collect_output()`, validate artifact. If missing sections exist, write `failure.json`, mark the step failed as retryable, and do not route handoff.

- [ ] **Step 5: Verify Task 8**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_artifact_contracts
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

### Task 9: Observability Commands

**Files:**
- Create: `src/at_flow/inspectors.py`
- Modify: `src/at_flow/cli.py`
- Modify: `src/at_flow/render.py`
- Test: `tests/test_observability_cli.py`
- Docs: `README.md`

**Interfaces:**
- Produces: `session_trace_summary(workspace: ATWorkspace, session_id: str) -> list[dict[str, Any]]`
- Produces: `session_audit_summary(workspace: ATWorkspace, session_id: str) -> list[dict[str, Any]]`
- Produces: CLI commands `trace`, `audit`, `artifact`, `doctor`

- [ ] **Step 1: Write failing observability test**

Create `tests/test_observability_cli.py` with a test that runs one mock `main` step and asserts `session_trace_summary()` includes:

```text
prepare_agent
build_context
collect_output
audit_permissions
```

- [ ] **Step 2: Verify the test fails**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_observability_cli
```

Expected:

```text
ModuleNotFoundError: No module named 'at_flow.inspectors'
```

- [ ] **Step 3: Implement inspectors**

Read `trace.jsonl`, `audit/*.json`, artifacts, failures, context paths, topic status, and provider config availability.

- [ ] **Step 4: Add CLI commands**

Add:

```text
trace <session-id>
audit <session-id>
artifact <session-id> <agent>
doctor
```

- [ ] **Step 5: Verify Task 9**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_observability_cli
$env:PYTHONPATH='src'; python .\at.py doctor
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

### Task 10: Retry, Abort, And Reroute Controls

**Files:**
- Modify: `src/at_flow/transitions.py`
- Modify: `src/at_flow/engine.py`
- Modify: `src/at_flow/cli.py`
- Test: `tests/test_runtime_contracts.py`
- Test: `tests/test_cli_controls.py`
- Docs: `docs/runtime-contracts.md`

**Interfaces:**
- Produces: `abort_session(session: SessionState, reason: str) -> None`
- Produces: `reset_downstream_steps(session: SessionState, from_index: int) -> None`
- Produces: CLI commands `abort`, `reroute`

- [ ] **Step 1: Write failing transition tests**

Add tests asserting:

```text
abort_session() marks queued/running/retrying steps aborted
reset_downstream_steps() keeps prior done steps and resets the selected step plus downstream
```

- [ ] **Step 2: Verify the tests fail**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_runtime_contracts
```

Expected:

```text
NameError: name 'abort_session' is not defined
```

- [ ] **Step 3: Implement transition helpers**

`abort_session()` sets session status to `aborted`, writes the reason, and finishes non-done steps.

`reset_downstream_steps()` clears step timestamps, artifact path, errors, failure reason, and input paths from the selected index onward.

- [ ] **Step 4: Add CLI controls**

Add:

```text
abort <session-id> --reason <reason>
reroute <session-id> --from <agent>
```

- [ ] **Step 5: Verify Task 10**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_runtime_contracts tests.test_cli_controls
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

### Task 11: Approval Guard

**Files:**
- Create: `src/at_flow/approvals.py`
- Modify: `src/at_flow/workspace.py`
- Modify: `src/at_flow/cli.py`
- Modify: `src/at_flow/engine.py`
- Test: `tests/test_approvals.py`
- Docs: `docs/runtime-contracts.md`
- Docs: `README.md`

**Interfaces:**
- Produces: `ApprovalRequest`
- Produces: `create_approval(workspace: ATWorkspace, session_id: str, action: str, risk: str, command: str) -> ApprovalRequest`
- Produces: `confirm_approval(workspace: ATWorkspace, token: str) -> ApprovalRequest`
- Produces: `consume_approval(workspace: ATWorkspace, token: str, session_id: str, action: str) -> ApprovalRequest`
- Produces: CLI commands `approval list`, `confirm`

- [ ] **Step 1: Write failing approval tests**

Create `tests/test_approvals.py`:

```python
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.approvals import confirm_approval, consume_approval, create_approval
from at_flow.workspace import ATWorkspace, WorkspaceError


class ApprovalTests(unittest.TestCase):
    def test_approval_token_is_single_use_and_session_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            request = create_approval(workspace, "session-a", "delete files", "destructive", "Remove-Item x")
            confirm_approval(workspace, request.token)

            consumed = consume_approval(workspace, request.token, "session-a", "delete files")

            self.assertEqual(consumed.token, request.token)
            with self.assertRaises(WorkspaceError):
                consume_approval(workspace, request.token, "session-a", "delete files")
```

- [ ] **Step 2: Verify the test fails**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_approvals
```

Expected:

```text
ModuleNotFoundError: No module named 'at_flow.approvals'
```

- [ ] **Step 3: Implement approval storage**

Create:

```text
.at/approvals/pending/
.at/approvals/used/
```

Approval JSON fields:

```json
{
  "schema_version": 1,
  "token": "8f31a2c0",
  "session_id": "session-a",
  "action": "delete files",
  "risk": "destructive",
  "command": "Remove-Item x",
  "status": "pending",
  "created_at": "...",
  "confirmed_at": null,
  "used_at": null,
  "expires_at": "..."
}
```

- [ ] **Step 4: Add CLI approval commands**

Add:

```text
approval list
confirm <token>
```

Conversation alias:

```text
AT: confirm <token>
```

- [ ] **Step 5: Add timeline and trace events**

On create, confirm, and consume, write trace events. If active topic exists, append timeline entries of kind `approval`.

- [ ] **Step 6: Verify Task 11**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_approvals
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

### Task 12: Provider Capability Checks

**Files:**
- Create: `src/at_flow/provider_checks.py`
- Modify: `src/at_flow/cli.py`
- Test: `tests/test_provider_checks.py`
- Docs: `README.md`

**Interfaces:**
- Produces: `ProviderCheck`
- Produces: `check_provider_capability(name: str, config: dict[str, Any]) -> ProviderCheck`
- Produces: CLI command `providers`

- [ ] **Step 1: Write failing provider check test**

Create `tests/test_provider_checks.py` with a missing executable config and assert:

```text
available is False
reason contains "command not found"
```

- [ ] **Step 2: Verify the test fails**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_provider_checks
```

Expected:

```text
ModuleNotFoundError: No module named 'at_flow.provider_checks'
```

- [ ] **Step 3: Implement provider checks**

Use `shutil.which()` for process providers. Mock providers are available without command checks. The check must not execute provider commands.

- [ ] **Step 4: Add CLI command**

Add:

```text
providers
```

It prints provider name, type, command, and availability.

- [ ] **Step 5: Verify Task 12**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_provider_checks
$env:PYTHONPATH='src'; python .\at.py providers
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

### Task 13: End-To-End Scenario Suite

**Files:**
- Create: `tests/test_e2e_scenarios.py`
- Modify: `tests/test_context_memory_contracts.py`
- Modify: `tests/test_sandbox.py`
- Docs: `docs/runtime-contracts.md`

**Interfaces:**
- Consumes public runtime and CLI behavior only.
- Produces regression coverage across topic, session, context, memory, approval, retry, audit, and rendering.

- [ ] **Step 1: Write E2E test for multiple sessions and topics**

Create `tests/test_e2e_scenarios.py` with a scenario that:

```text
initializes workspace
creates topic A and topic B
switches active topic
creates two sessions
runs one mock step for each session
asserts contexts and handoff files stay session-local
asserts active topic remains the selected topic
```

- [ ] **Step 2: Write E2E test for save-session timeline**

Scenario:

```text
create topic
run mock session
save session archive
assert archive exists
assert timeline contains session id
assert panel shows recent timeline
```

- [ ] **Step 3: Write E2E test for approval**

Scenario:

```text
create approval
confirm token
consume token
assert second consume fails
assert timeline records approval
```

- [ ] **Step 4: Verify Task 13**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_e2e_scenarios
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

### Task 14: Conversation ASCII Polish

**Files:**
- Modify: `src/at_flow/render.py`
- Modify: `src/at_flow/codex_trigger.py`
- Modify: `README.md`
- Test: `tests/test_render.py`
- Test: `tests/test_codex_trigger.py`

**Interfaces:**
- Consumes session status, active topic, recent timeline, trace/audit/artifact availability.
- Produces clearer `panel --format chat`, `status --format chat`, and Codex trigger instructions.

- [ ] **Step 1: Write failing render test for Baize-style continuity**

Add to `tests/test_render.py`:

```python
def test_panel_shows_topic_timeline_before_codex_layer(self) -> None:
    rendered = render_chat_panel(active_topic_name="AT Runtime", recent_timeline=["16:20 context contract"])

    self.assertIn("AT STATE MACHINE", rendered)
    self.assertIn("AT Runtime", rendered)
    self.assertIn("Recent Timeline", rendered)
    self.assertLess(rendered.index("AT STATE MACHINE"), rendered.index("Codex Execution Layer"))
```

- [ ] **Step 2: Verify the test fails**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_render
```

Expected:

```text
TypeError: render_chat_panel() got an unexpected keyword argument
```

- [ ] **Step 3: Update panel/status order**

Keep this order:

```text
AT Control Panel
AT State Machine
Topic Summary
Recent Timeline
Current Session
Command Menu
Runtime Evidence
Codex Execution Layer
```

- [ ] **Step 4: Update Codex trigger instructions**

`src/at_flow/codex_trigger.py` must instruct Codex:

```text
Always show AT state machine first, then topic/timeline context, current stage, runtime evidence, and Codex execution layer last.
```

- [ ] **Step 5: Verify Task 14**

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest tests.test_render tests.test_codex_trigger
$env:PYTHONPATH='src'; python .\at.py panel --format chat
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Expected:

```text
OK
```

---

## Execution Rules

- Execute tasks in numeric order.
- Do not start Topic runtime until Task 1 is verified.
- Do not start Timeline archive until Task 2 is verified.
- Do not start SOP/persona work until topic context exists.
- Do not start ASCII polish until Tasks 1-13 are verified.
- When verification fails, stay on the current task and fix it before continuing.
- Keep docs updates inside the task that changes behavior.
- Every final development report must include exact commands run and their results.

## Final Verification For The Whole Plan

Run:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests
$env:PYTHONPATH='src'; python -m compileall src tests at.py
$env:PYTHONPATH='src'; python .\at.py panel --format chat
$env:PYTHONPATH='src'; python .\at.py --help
```

Expected:

```text
all unittest files pass
compileall exits 0
panel prints the AT ASCII state machine with topic and recent timeline when available
help lists the implemented commands
```

## Self-Review

Spec coverage:

- Topic mode is covered by Tasks 2, 3, 4, 13, and 14.
- Timeline memory is covered by Tasks 3, 7, 11, 13, and 14.
- Session archive is covered by Task 3.
- SOP routing is covered by Task 5.
- Persona overlays are covered by Task 6.
- Context governance is covered by Task 4.
- Memory proposal review is covered by Task 7.
- Artifact and handoff validation is covered by Task 8.
- Observability is covered by Task 9.
- Recovery, retry, abort, and reroute are covered by Tasks 1 and 10.
- Approval guard is covered by Task 11.
- Provider safety is covered by Task 12.
- E2E confidence is covered by Task 13.
- Baize-style human interaction is covered by Task 14.

Plan quality:

- This plan has one canonical file path.
- Every task has files, interfaces, steps, test commands, and verification expectations.
- Runtime and safety work precede UI polish.
- Persona and SOP are explicitly forbidden from overriding `permissions.json`.

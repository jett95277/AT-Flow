# AT V1.6 Codex Provider And Dual Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AT Flow keep both usage modes while prioritizing mature Codex CLI capability as the default code-agent provider.

**Architecture:** AT remains the runtime and orchestrator. Codex, opencode, and OpenAI API are provider adapters behind the same session/state/artifact/audit contract. The Web Console and Codex conversation panel are two entry surfaces over the same AT runtime, not two separate products.

**Tech Stack:** Python runtime, FastAPI backend, React Web Console, Codex CLI process provider, existing `.at` workspace/session layout.

## Global Constraints

- AT owns state transitions, context construction, permissions, handoff, artifact validation, trace, audit, and retry.
- Codex is reused as a mature code-agent provider, but it must not become the flow owner.
- `agent.md` restricts role and side effects, not engineering capability.
- `permissions.json`, private workspaces, and post-run audit enforce hard boundaries.
- The previous Codex conversation/CLI mode must remain supported.
- The Web Console must use the same backend runtime and provider adapters.
- GPT/OpenAI API is optional provider infrastructure, not a replacement for Codex.
- Frontend display language can be Chinese while runtime prompts and artifacts can be English through a language contract.

---

## Product Decision

AT Flow has two supported usage modes:

```text
Mode A: Codex Conversation Mode
User -> Codex chat -> AT ASCII/status panel -> AT runtime -> provider adapter
```

```text
Mode B: Web Console Mode
User -> Web frontend -> FastAPI backend -> AT runtime -> provider adapter
```

Both modes must converge on the same runtime:

```text
AT Runtime
  -> session state
  -> agent context
  -> prompt builder
  -> provider adapter
  -> artifact/audit/trace
```

Provider priority:

```text
code/test agent: codex-cli first
main/analysis agent: codex-cli or openai-api depending on task
mock: test-only fallback
opencode: alternative code-agent provider
```

The platform must not collapse into:

```text
Web frontend -> FastAPI -> GPT API
```

That path is allowed only as one provider route:

```text
Web frontend -> FastAPI -> AT Runtime -> openai-api provider
```

## Agent Boundary Principle

Each agent keeps its own `agent.md`, but that file must not weaken Codex's code-agent capability.

Correct boundary:

```text
Codex capability is reused fully.
Agent boundary is enforced strictly.
Role restriction must not become capability degradation.
```

`agent.md` may restrict:

- role and responsibility
- allowed input sources
- required artifact format
- handoff expectations
- what must not be decided by this agent
- when to stop and report uncertainty

`agent.md` must not over-restrict:

- reading relevant local project files
- using engineering judgment
- running relevant checks
- producing necessary implementation changes within authorized scope
- explaining when broader changes are required

Hard enforcement belongs to:

```text
permissions.json
private agent workspace
context.json selected files
post-run permission audit
artifact contract validation
state transition rules
```

## File Structure

- Modify: `at.config.json`
  - Add provider routing defaults such as `agent_providers`.
- Modify: `src/at_flow/config.py`
  - Add default provider routing config.
- Modify: `src/at_flow/models.py`
  - Preserve session-level provider while allowing per-agent provider resolution.
- Modify: `src/at_flow/engine.py`
  - Resolve provider per agent step.
- Modify: `src/at_flow/providers.py`
  - Harden process provider command construction for Codex CLI and future opencode.
- Modify: `src/at_flow/web/app.py`
  - Let Web Console create sessions with provider mode or per-agent routing.
- Modify: `web/src/components/RunControls.tsx`
  - Add provider selection only after backend contract exists.
- Modify: `src/at_flow/codex_trigger.py`
  - Keep conversation mode explicitly documented and stable.
- Test: `tests/test_provider_routing.py`
  - Verify code/test prefer Codex when configured.
- Test: `tests/test_codex_trigger.py`
  - Verify Codex conversation mode still shows AT state before provider execution.
- Test: `tests/test_web_api.py`
  - Verify Web session creation uses runtime provider routing.
- Docs: `README.md`
  - Document the two official usage modes.

---

### Task 1: Provider Routing Contract

**Files:**
- Modify: `at.config.json`
- Modify: `src/at_flow/config.py`
- Create: `tests/test_provider_routing.py`

**Interfaces:**
- Consumes: existing `workspace.config`
- Produces: `resolve_agent_provider(config: dict, session_provider: str, agent: str) -> str`

- [x] **Step 1: Write the failing test**

Create `tests/test_provider_routing.py`:

```python
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.providers import resolve_agent_provider
from at_flow.workspace import ATWorkspace


class ProviderRoutingTests(unittest.TestCase):
    def test_agent_provider_route_overrides_session_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            workspace.config["agent_providers"] = {
                "main": "mock",
                "analysis": "mock",
                "code": "codex",
                "test": "codex",
            }

            self.assertEqual(resolve_agent_provider(workspace.config, "mock", "code"), "codex")
            self.assertEqual(resolve_agent_provider(workspace.config, "mock", "test"), "codex")

    def test_session_provider_is_fallback_when_no_agent_route_exists(self):
        self.assertEqual(resolve_agent_provider({}, "mock", "main"), "mock")


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m unittest tests.test_provider_routing
```

Expected: FAIL because `resolve_agent_provider` does not exist.

- [x] **Step 3: Implement provider routing**

In `src/at_flow/providers.py`, add:

```python
def resolve_agent_provider(config: dict[str, Any], session_provider: str, agent: str) -> str:
    routes = config.get("agent_providers", {})
    if isinstance(routes, dict):
        route = routes.get(agent)
        if isinstance(route, str) and route.strip():
            return route
    return session_provider
```

In default config, add:

```json
"agent_providers": {
  "main": "mock",
  "analysis": "mock",
  "code": "codex",
  "test": "codex"
}
```

For local tests, keep session provider default as `mock`; do not make Codex mandatory for unit tests.

- [x] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m unittest tests.test_provider_routing
```

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add at.config.json src/at_flow/config.py src/at_flow/providers.py tests/test_provider_routing.py
git commit -m "feat: add per-agent provider routing"
```

---

### Task 2: Engine Uses Per-Agent Provider

**Files:**
- Modify: `src/at_flow/engine.py`
- Test: `tests/test_provider_routing.py`

**Interfaces:**
- Consumes: `resolve_agent_provider(config, session_provider, agent)`
- Produces: engine step execution uses the resolved provider for the current agent.

- [ ] **Step 1: Write the failing test**

Extend `tests/test_provider_routing.py`:

```python
from at_flow.engine import Runner
from at_flow.models import SessionState


def test_engine_uses_agent_provider_route_for_code_step(self):
    with tempfile.TemporaryDirectory() as directory:
        workspace = ATWorkspace.init(Path(directory))
        workspace.config["agent_providers"] = {"code": "mock"}
        session = SessionState.new(
            task="route code",
            project_path=workspace.projects_root / "default",
            provider="missing-provider",
            pipeline=["code"],
            session_id="route-code-session",
        )
        workspace.create_session(session)

        result = Runner(workspace).run("route-code-session", one_step=True)

        self.assertEqual(result.steps[0].status, "done")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m unittest tests.test_provider_routing
```

Expected: FAIL because engine still uses `session.provider`.

- [ ] **Step 3: Update engine**

In `Runner._run_step`, resolve provider immediately before `make_provider`:

```python
provider_name = resolve_agent_provider(self.workspace.config, session.provider, step.agent)
provider = make_provider(provider_name, self.workspace.config)
```

Do not mutate `session.provider`; session provider remains the requested high-level default.

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m unittest tests.test_provider_routing tests.test_engine
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/at_flow/engine.py tests/test_provider_routing.py
git commit -m "feat: route providers per agent step"
```

---

### Task 3: Codex Process Provider Contract

**Files:**
- Modify: `src/at_flow/providers.py`
- Modify: `docs/runtime-contracts.md`
- Test: `tests/test_provider_checks.py` if present, otherwise `tests/test_provider_routing.py`

**Interfaces:**
- Consumes: process provider config.
- Produces: Codex provider config remains process-based and auditable.

- [ ] **Step 1: Write the failing config test**

Add a test that asserts Codex config is present and process-based:

```python
def test_default_codex_provider_is_process_provider(self):
    with tempfile.TemporaryDirectory() as directory:
        workspace = ATWorkspace.init(Path(directory))

        codex = workspace.config["providers"]["codex"]

        self.assertEqual(codex["type"], "process")
        self.assertEqual(codex["command"][0], "codex")
        self.assertEqual(codex["cwd"], "workspace")
        self.assertEqual(codex["env_policy"], "minimal")
```

- [ ] **Step 2: Run test**

Run:

```powershell
python -m unittest tests.test_provider_routing
```

Expected: PASS if the current config already satisfies it, otherwise FAIL with the missing field.

- [ ] **Step 3: Harden docs and contract**

Document:

```text
Codex provider is invoked only for one bounded agent step.
Codex runs from the agent private workspace.
Codex receives prompt.md through the configured prompt mode.
Codex output is collected into artifact.md.
Codex cannot advance AT state directly.
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m unittest tests.test_provider_routing
```

- [ ] **Step 5: Commit**

```powershell
git add src/at_flow/providers.py docs/runtime-contracts.md tests/test_provider_routing.py
git commit -m "docs: define codex provider boundary"
```

---

### Task 4: Preserve Codex Conversation Mode

**Files:**
- Modify: `src/at_flow/codex_trigger.py`
- Modify: `tests/test_codex_trigger.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: existing `install-codex-trigger`.
- Produces: Codex conversation mode stays an official entry mode.

- [ ] **Step 1: Write the failing test**

In `tests/test_codex_trigger.py`, assert generated AGENTS.md includes:

```text
AT has two official usage modes
Codex Conversation Mode
Web Console Mode
AT state machine must be shown before Codex/provider execution
```

- [ ] **Step 2: Run test**

Run:

```powershell
python -m unittest tests.test_codex_trigger
```

Expected: FAIL until trigger text is updated.

- [ ] **Step 3: Update trigger block**

In `src/at_flow/codex_trigger.py`, add a concise entry-mode section:

```text
AT has two official usage modes:
1. Codex Conversation Mode: user interacts in Codex chat; AT renders status first.
2. Web Console Mode: user interacts in browser; backend calls the same AT runtime.

Codex is a mature code-agent provider. Use it as execution layer, not flow owner.
```

- [ ] **Step 4: Update README**

Add:

```text
AT Flow supports two official modes:
- Codex conversation mode
- Web Console mode
Both call the same runtime and provider adapters.
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m unittest tests.test_codex_trigger
```

- [ ] **Step 6: Commit**

```powershell
git add src/at_flow/codex_trigger.py tests/test_codex_trigger.py README.md
git commit -m "docs: preserve codex conversation mode"
```

---

### Task 5: Web Console Provider Selection

**Files:**
- Modify: `src/at_flow/web/app.py`
- Modify: `src/at_flow/web/runtime_service.py`
- Modify: `web/src/api/types.ts`
- Modify: `web/src/api/client.ts`
- Modify: `web/src/components/RunControls.tsx`
- Test: `tests/test_web_api.py`
- Test: `web/src/components/RunControls.test.tsx`

**Interfaces:**
- Consumes: existing `POST /api/sessions`.
- Produces: Web Console can create sessions with a selected provider mode.

- [ ] **Step 1: Write backend test**

Add to `tests/test_web_api.py`:

```python
def test_create_session_accepts_codex_provider(self):
    with tempfile.TemporaryDirectory() as directory:
        workspace = ATWorkspace.init(Path(directory))
        client = TestClient(create_app(directory))

        response = client.post("/api/sessions", json={"task": "demo", "provider": "codex"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session"]["provider"], "codex")
        self.assertTrue(workspace.state_path(response.json()["session"]["id"]).exists())
```

- [ ] **Step 2: Run backend test**

Run:

```powershell
python -m unittest tests.test_web_api
```

Expected: PASS if current endpoint already accepts provider strings.

- [ ] **Step 3: Add frontend provider selector**

Add a small select control to `RunControls`:

```text
Provider: mock | codex | opencode
```

Keep default as `mock` until Codex process execution is manually enabled.

- [ ] **Step 4: Update frontend API payload**

`createSession` payload must include selected provider:

```ts
client.createSession({ task: "Web 控制台演示任务", provider: selectedProvider })
```

- [ ] **Step 5: Run frontend tests**

Run:

```powershell
cd web
npm.cmd test -- --run
```

- [ ] **Step 6: Commit**

```powershell
git add src/at_flow/web/app.py src/at_flow/web/runtime_service.py web/src tests
git commit -m "feat: add web provider selection"
```

---

### Task 6: Language Contract And Prompt Policy Skill

**Files:**
- Create: `src/at_flow/language/__init__.py`
- Create: `src/at_flow/language/schemas.py`
- Create: `src/at_flow/language/adapter.py`
- Create: `.at/shared/skills/prompt-language-policy/SKILL.md`
- Create: `.at/shared/skills/prompt-language-policy/templates/agent-prompt.en.md`
- Create: `.at/shared/skills/prompt-language-policy/templates/display-summary.zh.md`
- Create: `.at/shared/skills/prompt-language-policy/glossary.md`
- Modify: `src/at_flow/engine.py`
- Test: `tests/test_language_contracts.py`

**Interfaces:**
- Produces: `LanguageProfile`
- Produces: `.at/sessions/<session-id>/language.json`
- Produces: agent `context.json` includes language fields.

- [ ] **Step 1: Write failing language contract test**

Create `tests/test_language_contracts.py`:

```python
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow.models import SessionState
from at_flow.workspace import ATWorkspace
from at_flow.engine import Runner


class LanguageContractTests(unittest.TestCase):
    def test_session_writes_language_contract_for_chinese_user_input(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = ATWorkspace.init(Path(directory))
            workspace.config["language"] = {
                "user": "zh",
                "runtime": "en",
                "display": "zh",
                "artifact_mode": "bilingual",
            }
            session = SessionState.new(
                task="帮我实现登录模块",
                project_path=workspace.projects_root / "default",
                provider="mock",
                pipeline=["main"],
                session_id="language-session",
            )
            workspace.create_session(session)

            Runner(workspace).run("language-session", one_step=True)

            language_path = workspace.session_dir("language-session") / "language.json"
            context_path = workspace.session_dir("language-session") / "agents" / "main" / "context.json"
            language = json.loads(language_path.read_text(encoding="utf-8"))
            context = json.loads(context_path.read_text(encoding="utf-8"))

            self.assertEqual(language["task_original"], "帮我实现登录模块")
            self.assertEqual(language["runtime_language"], "en")
            self.assertEqual(language["display_language"], "zh")
            self.assertIn("task_runtime", language)
            self.assertEqual(context["language"]["runtime_language"], "en")
```

- [ ] **Step 2: Run test**

Run:

```powershell
python -m unittest tests.test_language_contracts
```

Expected: FAIL because language module and file writing do not exist.

- [ ] **Step 3: Implement deterministic language adapter**

Initial implementation does not call LLM. It stores original Chinese and wraps runtime task with English policy:

```text
Execute this user task in English runtime context.
Original user task:
帮我实现登录模块
```

This is not token-optimal yet; it creates the stable contract before GPT translation is added.

- [ ] **Step 4: Add prompt policy skill**

Create `.at/shared/skills/prompt-language-policy/SKILL.md`:

```markdown
# Prompt Language Policy

Use English for agent runtime prompts, reasoning instructions, and `artifact.md`.
Use Chinese for user-facing summaries and Web Console display.
Keep trace and audit in original execution language.
Do not translate paths, command names, API names, or code identifiers.
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m unittest tests.test_language_contracts tests.test_context_memory_contracts
```

- [ ] **Step 6: Commit**

```powershell
git add src/at_flow/language tests/test_language_contracts.py .at/shared/skills/prompt-language-policy src/at_flow/engine.py
git commit -m "feat: add language contract"
```

---

### Task 7: Full Verification

**Files:**
- No new files unless fixing discovered defects.

**Interfaces:**
- Verifies both entry modes and provider routing remain stable.

- [ ] **Step 1: Run Python tests**

```powershell
python -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend tests**

```powershell
cd web
npm.cmd test -- --run
```

Expected: all tests pass.

- [ ] **Step 3: Run frontend build**

```powershell
cd web
npm.cmd run build
```

Expected: build passes. If Windows sandbox returns `EPERM` writing `web/dist`, rerun the same command with explicit approval and document that the fallback is permission-related.

- [ ] **Step 4: Run Web Console smoke**

Start backend and frontend, then verify:

```text
GET  /api/health -> 200
GET  /api/sessions -> 200
GET  /api/workspace/tree -> 200
POST /api/sessions provider=mock -> 200
```

- [ ] **Step 5: Run Codex conversation trigger smoke**

Use a temp project:

```powershell
python -m at_flow enable --target <temp-project>
```

Verify generated `AGENTS.md` contains both usage modes and says AT state is shown before provider execution.

- [ ] **Step 6: Commit**

```powershell
git status --short
git commit -m "test: verify v1.6 provider and dual entry flow"
```

---

## Self-Review

Spec coverage:

- Dual usage modes are covered in Product Decision and Task 4.
- Codex as preferred mature code-agent provider is covered in Product Decision, Task 1, Task 2, and Task 3.
- GPT/OpenAI API not replacing Codex is explicitly constrained.
- `agent.md` boundary versus Codex capability is covered in Agent Boundary Principle.
- Language contract plus skill direction is covered in Task 6.

Placeholder scan:

- No TBD/TODO placeholders.
- Each task has concrete files, tests, commands, and expected behavior.

Type consistency:

- `resolve_agent_provider(config, session_provider, agent)` is introduced in Task 1 and consumed by Task 2.
- `LanguageProfile` and `language.json` are introduced in Task 6 only after provider routing is stable.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-01-at-v1-6-codex-provider-and-dual-entry-plan.md`.

Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints.

# AT V1.6 Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the two V1.6 review defects: explicit Web/CLI provider selection must not be silently overridden, and the language contract must become the primary provider prompt task.

**Architecture:** Keep AT as the orchestrator. Provider routing becomes an explicit mode: `mock`, `codex`, and `opencode` mean "use this provider for every agent"; `auto` means "use per-agent routes from `agent_providers`". Language conversion remains a contract file, but the runtime prompt reads `task_runtime` as the primary executable task and preserves the original user task as metadata.

**Tech Stack:** Python standard library runtime, FastAPI backend, React/Vite frontend, unittest backend tests, Vitest frontend tests.

## Global Constraints

- Do not add dependencies.
- Do not remove CLI mode or Web Console mode.
- Do not silently fall back from a selected provider to another provider.
- Preserve `agent.md`, `permissions.json`, artifact validation, trace, audit, and state transition ownership in AT.
- UI text remains Chinese, except provider names and API field names.
- Every task must run its own focused tests before the next task begins.

---

## File Structure

- `src/at_flow/providers.py`
  - Owns provider construction and provider routing resolution.
  - Add explicit semantics for `session.provider == "auto"`.

- `src/at_flow/engine.py`
  - Consumes resolved provider name.
  - Keeps failure handling and state transitions unchanged.

- `src/at_flow/language/adapter.py`
  - Owns language profile construction and persisted `language.json`.
  - No provider execution logic belongs here.

- `src/at_flow/providers.py`
  - Owns prompt construction.
  - Update `build_prompt()` so `context.language["task_runtime"]` is the primary `Task`.

- `web/src/components/RunControls.tsx`
  - Displays provider mode selector.
  - Add `auto` as the explicit "按 Agent 自动路由" option.

- `web/src/components/AppShell.tsx`
  - Keeps default provider as `mock`.
  - Passes selected provider unchanged to backend.

- `tests/test_provider_routing.py`
  - Adds routing contract tests.

- `tests/test_language_contracts.py`
  - Adds prompt contract tests.

- `web/src/components/RunControls.test.tsx`
  - Adds frontend provider mode selector tests.

- `docs/runtime-contracts.md`
  - Documents provider routing semantics and language prompt semantics.

---

### Task 1: Provider Routing Contract

**Files:**
- Modify: `src/at_flow/providers.py`
- Test: `tests/test_provider_routing.py`
- Docs: `docs/runtime-contracts.md`

**Interfaces:**
- Consumes: `resolve_agent_provider(config: dict[str, Any], session_provider: str, agent: str) -> str`
- Produces: Same function signature, with these rules:
  - If `session_provider != "auto"`, return `session_provider`.
  - If `session_provider == "auto"` and `config["agent_providers"][agent]` exists, return that route.
  - If `session_provider == "auto"` and no route exists, return `config.get("default_provider", "mock")`.

- [ ] **Step 1: Write failing routing tests**

Add these tests to `tests/test_provider_routing.py`:

```python
def test_explicit_session_provider_overrides_agent_route(self):
    config = {"agent_providers": {"code": "codex"}}

    self.assertEqual(resolve_agent_provider(config, "mock", "code"), "mock")
    self.assertEqual(resolve_agent_provider(config, "opencode", "code"), "opencode")


def test_auto_provider_uses_agent_route(self):
    config = {"agent_providers": {"code": "codex", "test": "codex"}}

    self.assertEqual(resolve_agent_provider(config, "auto", "code"), "codex")
    self.assertEqual(resolve_agent_provider(config, "auto", "test"), "codex")


def test_auto_provider_falls_back_to_default_provider(self):
    config = {"agent_providers": {"code": "codex"}, "default_provider": "mock"}

    self.assertEqual(resolve_agent_provider(config, "auto", "main"), "mock")
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m unittest tests.test_provider_routing
```

Expected: at least `test_explicit_session_provider_overrides_agent_route` fails because current implementation returns the agent route before honoring the session provider.

- [ ] **Step 3: Implement minimal routing fix**

Change `resolve_agent_provider()` in `src/at_flow/providers.py` to:

```python
def resolve_agent_provider(config: dict[str, Any], session_provider: str, agent: str) -> str:
    if session_provider != "auto":
        return session_provider

    routes = config.get("agent_providers", {})
    if isinstance(routes, dict):
        route = routes.get(agent)
        if isinstance(route, str) and route.strip():
            return route

    default_provider = config.get("default_provider", "mock")
    if isinstance(default_provider, str) and default_provider.strip():
        return default_provider
    return "mock"
```

- [ ] **Step 4: Update existing test expectation**

Replace the old test named `test_agent_provider_route_overrides_session_provider` with `test_auto_provider_uses_agent_route`. The old behavior is now invalid because it silently overrides explicit user selection.

- [ ] **Step 5: Document provider mode semantics**

Add to `docs/runtime-contracts.md` under `Provider Contract`:

```markdown
Provider selection has two modes:

- Explicit provider mode: `mock`, `codex`, or `opencode` means every agent step uses that provider unless the session is changed explicitly.
- Auto provider mode: `auto` means AT resolves each agent through `agent_providers`; missing routes fall back to `default_provider` or `mock`.

AT must not silently override an explicit session provider with an agent route.
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
python -m unittest tests.test_provider_routing
```

Expected: all tests pass.

---

### Task 2: Web Provider Mode Selector

**Files:**
- Modify: `web/src/components/RunControls.tsx`
- Modify: `web/src/components/RunControls.test.tsx`
- Inspect only: `web/src/components/AppShell.tsx`

**Interfaces:**
- Consumes: `selectedProvider: string`
- Produces: provider selector options:
  - `mock`
  - `auto`
  - `codex`
  - `opencode`

- [ ] **Step 1: Write failing frontend test**

Add to `web/src/components/RunControls.test.tsx`:

```tsx
it("offers explicit auto routing without changing the default mock mode", () => {
  render(<RunControls activeSessionId="s1" selectedProvider="mock" {...actions} />);

  expect(screen.getByLabelText("Provider")).toHaveValue("mock");
  expect(screen.getByRole("option", { name: "mock" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "auto" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "codex" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "opencode" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
cd web
npm.cmd test -- --run RunControls
```

Expected: fails because `auto` is not currently listed.

- [ ] **Step 3: Add `auto` provider option**

Change `PROVIDERS` in `web/src/components/RunControls.tsx` to:

```tsx
const PROVIDERS = [
  { value: "mock", label: "mock" },
  { value: "auto", label: "auto" },
  { value: "codex", label: "codex" },
  { value: "opencode", label: "opencode" }
];
```

Keep `AppShell.tsx` default:

```tsx
const [selectedProvider, setSelectedProvider] = useState("mock");
```

- [ ] **Step 4: Run focused frontend tests**

Run:

```powershell
cd web
npm.cmd test -- --run RunControls
```

Expected: all RunControls tests pass.

---

### Task 3: Language Runtime Prompt Contract

**Files:**
- Modify: `src/at_flow/providers.py`
- Test: `tests/test_language_contracts.py`
- Docs: `docs/runtime-contracts.md`

**Interfaces:**
- Consumes: `AgentContext.language: dict[str, Any] | None`
- Produces:
  - `_task_for_prompt(context: AgentContext) -> str`
  - `build_prompt(context: AgentContext) -> str` uses `task_runtime` as the primary executable task.

- [ ] **Step 1: Write failing prompt test**

Add to `tests/test_language_contracts.py`:

```python
def test_provider_prompt_uses_runtime_task_as_primary_task(self):
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
            session_id="language-prompt-session",
        )
        workspace.create_session(session)

        Runner(workspace).run("language-prompt-session", one_step=True)

        prompt_path = workspace.session_agent_dir("language-prompt-session", "main") / "prompt.md"
        prompt = prompt_path.read_text(encoding="utf-8")

        task_section = prompt.split("Task:", 1)[1].split("Original User Task:", 1)[0]
        self.assertIn("Execute this user task in English runtime context.", task_section)
        self.assertIn("Original user task:", task_section)
        self.assertIn("帮我实现登录模块", task_section)
        self.assertIn("Original User Task:\n帮我实现登录模块", prompt)
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
python -m unittest tests.test_language_contracts
```

Expected: fails because current `Task:` section is still `context.session.task`.

- [ ] **Step 3: Add prompt task helper**

Add this helper near `build_prompt()` in `src/at_flow/providers.py`:

```python
def _task_for_prompt(context: AgentContext) -> str:
    language = context.language or {}
    task_runtime = language.get("task_runtime")
    if isinstance(task_runtime, str) and task_runtime.strip():
        return task_runtime.strip()
    return context.session.task
```

- [ ] **Step 4: Use runtime task in `build_prompt()`**

Change the prompt body in `build_prompt()` from:

```python
Task:
{context.session.task}
```

to:

```python
Task:
{_task_for_prompt(context)}

Original User Task:
{context.session.task}
```

- [ ] **Step 5: Document language prompt semantics**

Add to `docs/runtime-contracts.md` under `Provider Contract` or a new `Language Contract` subsection:

```markdown
When `language.json` contains `task_runtime`, AT uses it as the primary `Task`
inside provider prompts. The original user task is preserved separately as
`Original User Task` and in `language.task_original`.
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
python -m unittest tests.test_language_contracts
```

Expected: all language contract tests pass.

---

### Task 4: Integrated Regression Verification

**Files:**
- No source files unless a previous task exposed a defect.

**Interfaces:**
- Consumes:
  - `resolve_agent_provider(config, session_provider, agent)`
  - `build_prompt(context)`
  - Web provider selector
- Produces: verified V1.6 review fix branch.

- [ ] **Step 1: Run backend regression tests**

Run:

```powershell
python -m unittest discover -s tests
```

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend tests**

Run:

```powershell
cd web
npm.cmd test -- --run
```

Expected: all frontend tests pass.

- [ ] **Step 3: Build frontend**

Run:

```powershell
cd web
npm.cmd run build
```

Expected: build passes. If Windows sandbox blocks writing `web/dist`, rerun with explicit approval and record that escalation was required.

- [ ] **Step 4: Inspect diff**

Run:

```powershell
git diff --stat
git diff -- src/at_flow/providers.py tests/test_provider_routing.py tests/test_language_contracts.py web/src/components/RunControls.tsx web/src/components/RunControls.test.tsx docs/runtime-contracts.md
```

Expected: diff only contains review-fix changes and this plan file.

- [ ] **Step 5: Commit only after user approval**

Do not commit automatically. If the user approves committing, use:

```powershell
git add docs/superpowers/plans/2026-08-01-at-v1-6-review-fixes-plan.md src/at_flow/providers.py tests/test_provider_routing.py tests/test_language_contracts.py web/src/components/RunControls.tsx web/src/components/RunControls.test.tsx docs/runtime-contracts.md
git commit -m "fix: tighten provider and language contracts"
```

---

## Self-Review

- Spec coverage: covers both review findings.
- Provider boundary: explicit provider selection no longer silently changes execution provider.
- Language contract: `task_runtime` becomes the primary provider task.
- Test coverage: backend routing, backend prompt generation, frontend selector, full regression.
- Dependency impact: no new dependencies.
- Risk left: `codex` and `opencode` real process availability is still outside this fix; provider capability checks remain a separate runtime hardening task.

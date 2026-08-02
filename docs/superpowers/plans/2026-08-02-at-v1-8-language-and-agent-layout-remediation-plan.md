# AT V1.8 Language And Agent Layout Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Agent definitions out of the shared area and implement a real, observable Chinese-input/English-runtime/Chinese-display language pipeline.

**Architecture:** Canonical Agent packages move to `.at/agents` and continue to be snapshotted into each Session. A focused Language Service invokes one explicitly configured provider through a restricted text-translation boundary, persists Language Contract V2, supplies English-only runtime context, and creates separate Chinese display artifacts for the Web Console.

**Tech Stack:** Python 3 standard library, FastAPI, React, TypeScript, unittest, Vitest.

## Global Constraints

- Update `agent.md` before every implementation task.
- Write and run a failing targeted test before production code.
- Do not silently translate, fall back to the original text, or select another provider.
- Preserve `task_original` in Session state and `language.json` only.
- Do not expose project, shared memory, Agent inbox, or write permissions to translation execution.
- Keep English `artifact.md` as the only downstream handoff source.
- Keep Chinese `artifact.zh.md` as a display-only derivative.
- Do not add a translation microservice, OpenAI SDK, or other dependency.
- Do not create a branch, commit, or push in this development window.

## File Structure

- `src/at_flow/migrations.py`: explicit Agent-layout migration and collision checks.
- `src/at_flow/workspace.py`: canonical layout properties and Session package snapshots.
- `src/at_flow/language/schemas.py`: Language Contract V2 value objects and serialization.
- `src/at_flow/language/translator.py`: restricted text translator protocol and process implementation.
- `src/at_flow/language/service.py`: input/display translation lifecycle and persisted statuses.
- `src/at_flow/providers.py`: reusable process-prompt runner and English provider prompt.
- `src/at_flow/engine.py`: language lifecycle integration, trace events, and display artifact generation.
- `src/at_flow/context_contracts.py`: provider-safe English runtime context.
- `src/at_flow/web/runtime_service.py`: structured language and artifact reads.
- `web/src/components/LanguageStatus.tsx`: visible language path and failure status.
- `web/src/components/RuntimeEvidence.tsx`: Chinese display artifact with explicitly labelled English source.

---

### Task 1: Canonical Agent Layout And Explicit Migration

**Files:**
- Create: `src/at_flow/migrations.py`
- Create: `tests/test_agent_layout_migration.py`
- Modify: `src/at_flow/config.py`
- Modify: `src/at_flow/workspace.py`
- Modify: `src/at_flow/cli.py`
- Modify: `src/at_flow/web/workspace_service.py`
- Modify: `tests/test_web_workspace_service.py`
- Modify: `agent.md`

**Interfaces:**
- Produces: `AgentLayoutMigration` dataclass with `source`, `target`, `status`, and `moved_files`.
- Produces: `migrate_agent_layout(root: Path, *, apply: bool) -> AgentLayoutMigration`.
- Produces: CLI `migrate-agent-layout [--apply]`.
- Changes default `workspace.agents_dir` from `.at/shared/agents` to `.at/agents`.

- [x] **Step 1: Update `agent.md` to Task 1 in progress**

Record the task name, expected tests, and that no Git operation is allowed.

- [x] **Step 2: Write failing layout and migration tests**

Add tests equivalent to:

```python
def test_fresh_workspace_puts_agent_definitions_outside_shared():
    workspace = ATWorkspace.init(root)
    assert workspace.agents_root == (root / ".at" / "agents").resolve()
    assert (root / ".at" / "agents" / "main" / "agent.md").exists()
    assert not (root / ".at" / "shared" / "agents").exists()

def test_migration_moves_legacy_packages_and_updates_config_only_when_applied():
    preview = migrate_agent_layout(root, apply=False)
    assert preview.status == "preview"
    assert legacy.exists()
    applied = migrate_agent_layout(root, apply=True)
    assert applied.status == "migrated"
    assert not legacy.exists()
    assert target.joinpath("main", "agent.md").exists()
    assert json.loads(config.read_text())["workspace"]["agents_dir"] == ".at/agents"

def test_migration_refuses_non_empty_target():
    with self.assertRaises(MigrationError):
        migrate_agent_layout(root, apply=True)
```

Also change the workspace-tree test so `shared/agents` is absent because it is
physically absent, while top-level `agents/main/agent.md` remains visible.

- [x] **Step 3: Run tests and confirm the old layout fails**

Run:

```powershell
python -m unittest tests.test_agent_layout_migration tests.test_web_workspace_service
```

Expected: FAIL because the default remains `.at/shared/agents` and no migration interface exists.

- [x] **Step 4: Implement collision-safe migration and new default**

`migrate_agent_layout` must:

```python
legacy = root.resolve() / ".at" / "shared" / "agents"
target = root.resolve() / ".at" / "agents"
```

- return `not_needed` when config already points to `.at/agents` and no legacy directory exists;
- return `preview` without writes when `apply=False`;
- refuse an existing non-empty target;
- move the complete legacy directory before updating the JSON config;
- update only `workspace.agents_dir` and preserve all other config fields;
- report every moved file as a relative POSIX path.

The workspace tree excludes `shared/agents` only when the configured
`agents_root` is exactly `shared_root / "agents"`; it must not hide an unrelated
user-created shared folder named `agents` after migration.

- [x] **Step 5: Add CLI command and run targeted tests**

Run:

```powershell
python -m unittest tests.test_agent_layout_migration tests.test_web_workspace_service tests.test_codex_trigger
```

Expected: PASS.

- [x] **Step 6: Inspect Task 1 diff**

Run:

```powershell
git diff --check -- src/at_flow/config.py src/at_flow/workspace.py src/at_flow/migrations.py src/at_flow/cli.py src/at_flow/web/workspace_service.py tests/test_agent_layout_migration.py tests/test_web_workspace_service.py agent.md
```

Expected: no whitespace errors.

---

### Task 2: Restricted Translation Provider Boundary

**Files:**
- Create: `src/at_flow/language/translator.py`
- Create: `tests/test_language_translator.py`
- Modify: `src/at_flow/providers.py`
- Modify: `src/at_flow/language/__init__.py`
- Modify: `agent.md`

**Interfaces:**
- Produces: `TranslationError(code: str, message: str, retryable: bool)`.
- Produces: `TextTranslator.translate(text: str, source_language: str, target_language: str, purpose: str) -> str`.
- Produces: `make_text_translator(config: dict[str, Any], provider_name: str, work_dir: Path) -> TextTranslator`.
- Produces: `run_process_prompt(name, provider_config, prompt, *, cwd, env_overrides) -> str` in `providers.py`.

- [x] **Step 1: Update `agent.md` to Task 2 in progress**

- [x] **Step 2: Write failing translator tests**

Use a temporary process provider based on `sys.executable -c` so the test proves
that actual process output is used rather than a wrapper string:

```python
translator = make_text_translator(config, "translator", work_dir)
translated = translator.translate("帮我实现登录模块", "zh", "en", "task")
self.assertEqual(translated, "Implement a login module for me")
self.assertFalse((work_dir / "project").exists())
```

Add cases for unknown provider, mock provider rejection, non-zero exit, empty
output, and unchanged output when languages differ.

- [x] **Step 3: Run tests and confirm failure**

```powershell
python -m unittest tests.test_language_translator
```

Expected: FAIL because `translator.py` and `run_process_prompt` do not exist.

- [x] **Step 4: Extract process execution and implement translator**

The translation prompt must request only translated text and contain no AT
workspace paths. The process environment may include the configured minimal
passthrough plus:

```text
AT_TRANSLATION_SOURCE
AT_TRANSLATION_TARGET
AT_TRANSLATION_PURPOSE
```

It must not include `AT_PROJECT_PATH`, `AT_SHARED_*`, `AT_AGENT_*`, or Session
control paths. Reject empty output and exact unchanged output when source and
target differ.

- [x] **Step 5: Run translator and provider regression tests**

```powershell
python -m unittest tests.test_language_translator tests.test_provider_capabilities tests.test_provider_routing
```

Expected: PASS.

---

### Task 3: Language Contract V2 And Input Translation Lifecycle

**Files:**
- Create: `src/at_flow/language/service.py`
- Modify: `src/at_flow/language/schemas.py`
- Modify: `src/at_flow/language/adapter.py`
- Modify: `src/at_flow/language/__init__.py`
- Modify: `src/at_flow/config.py`
- Modify: `src/at_flow/engine.py`
- Modify: `tests/test_language_contracts.py`
- Modify: `tests/test_engine.py`
- Modify: `agent.md`

**Interfaces:**
- Produces: `TranslationState(status, provider, error, updated_at)`.
- Produces: Language Contract schema version `2`.
- Produces: `LanguageService.ensure_runtime_profile(session) -> dict[str, Any]`.
- Produces: `LanguageService.translate_artifact(session, agent, source_path) -> Path | None` for Task 5.
- Runner accepts optional `language_service_factory` for deterministic unit tests.

- [x] **Step 1: Update `agent.md` to Task 3 in progress**

- [x] **Step 2: Replace wrapper assertions with failing real-translation tests**

The input test must assert:

```python
self.assertEqual(language["schema_version"], 2)
self.assertEqual(language["task_original"], "帮我实现登录模块")
self.assertEqual(language["task_runtime"], "Implement a login module for me")
self.assertEqual(language["input_translation"]["status"], "completed")
self.assertEqual(language["input_translation"]["provider"], "test-translator")
```

Add tests for:

- English input detected as English and marked `not_required`;
- failed required translation fails the current step before Agent provider run;
- retry re-attempts a failed translation;
- an existing completed V2 profile is reused;
- a legacy V1 profile whose task still contains Chinese is not treated as completed.

- [x] **Step 3: Run tests and confirm existing fake translation fails**

```powershell
python -m unittest tests.test_language_contracts tests.test_engine
```

Expected: FAIL because `task_runtime` still contains the original Chinese task and status remains `pending`.

- [x] **Step 4: Implement schema V2 and Language Service**

Use these fresh-workspace defaults:

```python
"language": {
    "enabled": False,
    "source": "auto",
    "runtime": "en",
    "display": "zh",
    "translation_provider": "",
    "required": True,
    "translate_artifacts": True,
}
```

The current workspace explicitly enables conversion and selects `codex` in Task
7. `source="auto"` uses a deterministic CJK check for `zh`; otherwise it uses
`en`. Disabled conversion records `disabled` and does not claim an English
runtime for Chinese input. Enabled input translation writes `running` before
invoking the translator, then `completed` or `failed`. A failed required
translation raises a typed `LanguageError` that Runner records as a retryable
failed step and trace event.

- [x] **Step 5: Run targeted tests**

```powershell
python -m unittest tests.test_language_contracts tests.test_engine tests.test_runtime_contracts
```

Expected: PASS.

---

### Task 4: English-Only Runtime Prompt And Handoff Contract

**Files:**
- Modify: `src/at_flow/context_contracts.py`
- Modify: `src/at_flow/providers.py`
- Modify: `src/at_flow/agent_profiles.py`
- Modify: `src/at_flow/artifacts.py`
- Modify: `tests/test_language_contracts.py`
- Modify: `tests/test_artifact_contracts.py`
- Modify: `tests/test_context_memory_contracts.py`
- Modify: `agent.md`

**Interfaces:**
- Produces: `runtime_language_view(language: dict[str, Any]) -> dict[str, Any]` without `task_original`.
- Produces: `validate_runtime_artifact_language(artifact: str, runtime_language: str) -> list[str]`.

- [x] **Step 1: Update `agent.md` to Task 4 in progress**

- [x] **Step 2: Write failing prompt and artifact tests**

Assert the final `prompt.md`:

```python
self.assertIn("Implement a login module for me", prompt)
self.assertNotIn("帮我实现登录模块", prompt)
self.assertNotIn('"task_original"', prompt)
```

Assert `context.json["task"]` is English and its embedded language view excludes
`task_original`. Add an artifact-language test that ignores fenced code blocks
but reports CJK narrative outside code fences for an English runtime.

- [x] **Step 3: Run tests and confirm Chinese leaks through context**

```powershell
python -m unittest tests.test_language_contracts tests.test_artifact_contracts tests.test_context_memory_contracts
```

Expected: FAIL because the prompt embeds the original Session task and full language profile.

- [x] **Step 4: Sanitize provider context and enforce source artifact language**

- use `task_runtime` for provider-facing `context.json["task"]`;
- expose only language codes, translation status, and runtime task in provider context;
- remove the `Original User Task` prompt section after completed translation;
- change MockProvider artifact Task to runtime task;
- validate narrative language outside fenced code blocks before a step becomes done;
- return a retryable artifact contract failure when English narrative contains CJK.

- [x] **Step 5: Run targeted tests**

```powershell
python -m unittest tests.test_language_contracts tests.test_artifact_contracts tests.test_context_memory_contracts tests.test_engine
```

Expected: PASS.

---

### Task 5: Chinese Display Artifact And Structured Backend API

**Files:**
- Modify: `src/at_flow/language/service.py`
- Modify: `src/at_flow/engine.py`
- Modify: `src/at_flow/web/schemas.py`
- Modify: `src/at_flow/web/runtime_service.py`
- Modify: `src/at_flow/web/app.py`
- Modify: `tests/test_language_contracts.py`
- Modify: `tests/test_web_api.py`
- Modify: `tests/test_web_runtime_service.py`
- Modify: `agent.md`

**Interfaces:**
- Produces: `GET /api/sessions/{session_id}/language`.
- Changes artifact response to `ArtifactView` with `source`, `display`,
  `source_language`, `display_language`, `display_status`, `display_provider`, and
  `display_error`.

- [x] **Step 1: Update `agent.md` to Task 5 in progress**

- [x] **Step 2: Write failing display translation and API tests**

Verify successful output creates:

```text
.at/sessions/<id>/agents/<agent>/outbox/artifact.md
.at/sessions/<id>/agents/<agent>/outbox/artifact.zh.md
```

Assert handoff content equals English `artifact.md`, not `artifact.zh.md`.
Assert a display translation failure leaves the Agent step done, preserves the
English source, writes `display_translation.status=failed`, and returns a typed
structured API response.

- [x] **Step 3: Run tests and confirm no display artifact exists**

```powershell
python -m unittest tests.test_language_contracts tests.test_web_api tests.test_web_runtime_service
```

Expected: FAIL because the runtime only returns a raw English artifact string.

- [x] **Step 4: Implement display translation after source validation**

Run display translation after English artifact validation but before routing the
English handoff. Persist status and trace events. Display translation failure is
observable but does not invalidate a valid engineering artifact.

The API must return `display=None` unless translation completed; it must never
copy `source` into `display` as a fallback.

- [x] **Step 5: Run targeted backend tests**

```powershell
python -m unittest tests.test_language_contracts tests.test_web_api tests.test_web_runtime_service tests.test_engine
```

Expected: PASS.

---

### Task 6: Web Console Language Status And Chinese Display

**Files:**
- Create: `web/src/components/LanguageStatus.tsx`
- Create: `web/src/components/LanguageStatus.test.tsx`
- Modify: `web/src/api/types.ts`
- Modify: `web/src/api/client.ts`
- Modify: `web/src/api/client.test.ts`
- Modify: `web/src/components/AppShell.tsx`
- Modify: `web/src/components/AppShell.test.tsx`
- Modify: `web/src/components/RuntimeEvidence.tsx`
- Modify: `web/src/components/RuntimeEvidence.test.tsx`
- Modify: `web/src/styles.css`
- Modify: `agent.md`

**Interfaces:**
- Produces: `LanguageProfile` and `ArtifactView` TypeScript types.
- Produces: `client.getLanguage(sessionId)`.
- Produces: `LanguageStatus` component.

- [x] **Step 1: Update `agent.md` to Task 6 in progress**

- [x] **Step 2: Write failing frontend tests**

Test these user-visible states:

```text
中文输入 -> 英文运行 -> 中文展示
输入翻译：已完成 / 失败 / 无需翻译
展示翻译：已完成 / 失败 / 等待产物
```

Verify RuntimeEvidence displays `artifact.display` as the primary artifact when
completed. On failure it shows the Chinese failure message and exposes the
English source only inside a labelled `<details>` element.

- [x] **Step 3: Run frontend tests and confirm types/components are missing**

```powershell
Set-Location web
npm.cmd test -- --run src/components/LanguageStatus.test.tsx src/components/RuntimeEvidence.test.tsx src/components/AppShell.test.tsx src/api/client.test.ts
```

Expected: FAIL.

- [x] **Step 4: Implement typed polling and display UI**

Poll Language Contract with the active Session. Reuse the existing stale-response
guard so an old Session cannot overwrite the selected Session's language state.
Clear language and artifact state on Session selection.

Keep the component compact and work-focused; do not add a new card inside a
card. Use status text and existing visual conventions.

- [x] **Step 5: Run targeted frontend tests and build**

```powershell
Set-Location web
npm.cmd test -- --run src/components/LanguageStatus.test.tsx src/components/RuntimeEvidence.test.tsx src/components/AppShell.test.tsx src/api/client.test.ts
npm.cmd run build
```

Expected: all tests pass and production build exits 0.

---

### Task 7: Current Workspace Migration, Documentation, And Full Verification

**Files:**
- Modify: `at.config.json`
- Move: `.at/shared/agents` to `.at/agents` through the migration command
- Modify: `src/at_flow/engine.py`
- Modify: `src/at_flow/providers.py`
- Modify: `src/at_flow/language/translator.py`
- Modify: `tests/test_language_translator.py`
- Modify: `tests/test_runtime_contracts.py`
- Modify: `.at/shared/skills/prompt-language-policy/SKILL.md`
- Modify: `docs/architecture.md`
- Modify: `docs/runtime-contracts.md`
- Modify: `docs/superpowers/plans/2026-08-02-at-v1-8-codex-capability-implementation-plan.md`
- Modify: `README.md`
- Modify: `agent.md`
- Create: `.at/shared/skills/language-translation/SKILL.md`
- Create: `.at/shared/skills/language-translation/glossary.md`
- Create: Chinese display copies for every Agent contract document
  (`.at/agents/<agent>/agent.zh.md`, `output.zh.md`; JSON stays English)
- Create: `docs/superpowers/specs/2026-08-02-at-v1-8-language-translation-skill-design.md`
- Modify: `src/at_flow/language/translator.py` (skill instruction loading)
- Modify: `src/at_flow/language/service.py` (skill_dir injection)
- Modify: `src/at_flow/web/workspace_service.py` (zh display copies, tree hide)
- Modify: `src/at_flow/web/app.py` (`language` query parameter)
- Modify: `web/src/api/client.ts` and its test (request `language=zh`)

**Interfaces:**
- Current workspace uses `.at/agents`.
- Documentation distinguishes Language Contract V1.6 origin from V1.8 remediation.
- Prompt-language Skill states that execution belongs to Language Service.

- [x] **Step 1: Update `agent.md` to Task 7 in progress**

- [x] **Step 2: Run migration preview and inspect paths**

```powershell
python .\at.py migrate-agent-layout
```

Expected: preview lists `.at/shared/agents` as source and `.at/agents` as target.

- [x] **Step 3: Apply the explicit migration**

Before moving, resolve and verify both paths are inside `E:\AT FLOW\.at`. Then run:

```powershell
python .\at.py migrate-agent-layout --apply
```

Expected: all four Agent packages move, config changes to `.at/agents`, and
`.at/shared/agents` no longer exists.

- [x] **Step 4: Update contracts and documentation**

Document:

- canonical Agent definitions versus Session snapshots;
- exact Chinese-input/English-runtime/Chinese-display flow;
- required translation provider configuration;
- explicit errors and no-fallback rule;
- token-cost caveat;
- live Codex translation result, latency, and any transport failure without
  substituting a deterministic test translator.

Set the current workspace language configuration explicitly to:

```json
{
  "enabled": true,
  "source": "auto",
  "runtime": "en",
  "display": "zh",
  "translation_provider": "codex",
  "translation_provider_overrides": {
    "command": [
      "codex",
      "exec",
      "--skip-git-repo-check",
      "--sandbox",
      "read-only",
      "--ephemeral",
      "--color",
      "never",
      "-"
    ],
    "timeout_seconds": 180
  },
  "required": true,
  "translate_artifacts": true
}
```

The translation boundary may override only the provider command and timeout.
It always forces stdin prompt mode, a minimal environment, a translation-only
working directory, and a separate successful-process stderr log. This prevents
Codex diagnostics from becoming translated content.

On Windows, configured `.cmd` and `.bat` process-provider launchers are executed
through `cmd.exe`; native executables remain direct child processes. Process
creation errors are converted to typed provider failures instead of escaping and
leaving a Session step in `running`.

Process execution uses an AT-owned lifecycle instead of fire-and-forget shell
semantics. Every provider gets a separate process group; a timeout terminates
the complete child tree before the typed timeout error is returned.

Session locks contain the owner PID. A dead owner is reclaimed atomically on the
next run so interrupted-step recovery remains reachable after a hard process
termination. Translation failure stderr stays in the private translation log;
durable language state stores only a concise error.

- [x] **Step 5: Run full backend verification**

```powershell
python -m unittest discover -s tests
```

Expected: all tests pass.

- [x] **Step 6: Run full frontend verification**

```powershell
Set-Location web
npm.cmd test -- --run
npm.cmd run build
```

Expected: all tests pass and build exits 0. If the sandbox blocks `web/dist`,
request explicit permission and rerun the same build command; record that fact.

- [x] **Step 7: Run integration and sandbox checks**

Verify:

```text
GET /api/health                         -> 200
GET /api/workspace/tree                 -> agents exists, shared/agents absent
GET /api/sessions/<id>/language         -> Language Contract V2
GET /api/sessions/<id>/artifact/<agent> -> structured ArtifactView
```

Run the existing sandbox suite and a controlled process-translator test. A live
Codex translation test is separate: if the executable is blocked, unauthenticated,
or non-interactive invocation is unknown, report it as unverified rather than
substituting the test translator.

- [x] **Step 8: Browser verification**

Use Playwright at desktop and mobile widths. Confirm:

- the tree has only top-level `agents`;
- Language Status shows the three-stage flow;
- Chinese display artifact and labelled English source do not overlap;
- all three panels remain independently usable.

Completed with explicit permission: `@playwright/cli` was downloaded with
escalation, the backend (8000) and frontend (3000) were started, and a real
browser session verified:

```text
GET /api/health                         -> 200
GET /api/workspace/tree                 -> agents/main/agent.md present,
                                           no agent.zh.md / output.zh.md
GET /api/file?path=agents/main/agent.md&language=zh -> Chinese contract text
GET /api/file?path=agents/main/agent.md&language=en -> English source
Browser: agents tree -> main -> agent.md shows 职责/负责事项/边界/输入/输出契约
Browser: output.md shows # main 输出契约 with 中英对照 section names
```

Desktop-width verification passed. Mobile-width screenshots were not captured;
the responsive CSS was exercised by the existing component tests only.

- [x] **Step 9: Final diff and plan status**

```powershell
git diff --check
git status --short
```

Mark every completed checkbox and set `agent.md` current task to `none`. Do not
stage, commit, or push.

`git diff --check` reported no whitespace errors. The working tree keeps all
V1.8 and V1.9 changes unstaged and uncommitted per the development window rule.

---

## V1.8 Completion Addendum: Translation Skill And Chinese Documents

During Task 7 completion the translation rules were moved from Python into a
platform skill:

- `.at/shared/skills/language-translation/SKILL.md` holds the translation
  execution rules (output contract, preservation rules, purpose semantics).
- `.at/shared/skills/language-translation/glossary.md` holds Chinese display
  terms for AT platform vocabulary.
- `ProcessTextTranslator` loads SKILL.md and glossary as prompt instructions
  when `skill_dir` is set. A missing SKILL.md raises
  `translation_skill_missing` (not retryable); no fallback to the old
  hard-coded prompt.
- `LanguageService` injects the skill directory
  (`<workspace>/.at/shared/skills/language-translation`) for both input and
  display translation.
- Fixed workspace documents now have reviewed Chinese display copies
  (`agent.zh.md`, `output.zh.md`). `WorkspaceService.read_file` prefers the
  Chinese copy by default and returns the English source with
  `language=en`. The workspace tree hides `*.zh.md` copies whose source
  exists. JSON configuration files are not translated.
- Frontend `getFile` requests `language=zh`.

Post-review cleanup (user request): the `LanguageStatus` panel was not part of
the user's original requirements. It was removed together with its test and
AppShell wiring (`LanguageStatus.tsx`, `LanguageStatus.test.tsx`, AppShell
state/interval calls, related CSS). The backend language API and `client.getLanguage`
remain; the frontend simply no longer displays the panel. Frontend suite after
removal: 38 tests passed, production build passed.

Verification recorded during this addendum:

```text
Backend suite: 124 tests passed (5 new tests for skill loading, missing skill,
display copies, and tree hiding)
Frontend suite: 41 tests passed (1 new client test for language=zh)
Production build: passed
Real-data check: read_file returns 职责/中文副本 for agent.md, English with
language=en, tree hides agent.zh.md and output.zh.md
```

Shared-area coverage added after review: `memory` (decisions/project/rules/user)
and `policies` (context/memory) now have Chinese display copies too. `skills/`
SKILL.md files stay English because they are runtime instructions loaded by the
translator and agents; translating them would break execution. Browser check
confirmed shared/memory/decisions.md and shared/policies/context.md render in
Chinese with English terms (context contract) preserved.

`quick_validate.py` from the skill-creator suite was not run because PyYAML is
not installed in the local Python environment; the SKILL.md structure was
checked manually (frontmatter name/description, folder naming, no extraneous
files). Live `codex exec` translation remains unverified because transport
failures occurred in this environment; it is reported separately, never
substituted by the deterministic test translator.

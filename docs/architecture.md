# AT Flow Architecture

## Purpose

AT Flow coordinates a small team of specialized CLI agents around one shared
project. It keeps agent responsibilities separate while giving every session
controlled access to shared memory, skills, and project files.

## Agent model

The default pipeline is serial:

1. `main`: frames the request, boundaries, and acceptance criteria.
2. `analysis`: turns the request into a plan, assumptions, and risk notes.
3. `code`: performs or describes implementation work.
4. `test`: verifies the result and records the final report.

The platform stores every agent artifact under that agent's own directory. The
handoff between agents is file based: later agents receive paths to earlier
artifacts instead of sharing one mutable conversation buffer.

Each agent also has a package containing `agent.md`, `permissions.json`, and
`output.md`. The shared copy lives at `.at/shared/agents/<agent>`; each session
receives a snapshot under `.at/sessions/<id>/agents/<agent>`.

## Isolation model

Physical isolation:

- each AT session has a dedicated directory under `.at/sessions`
- each agent has a dedicated directory under `.at/sessions/<id>/agents`
- process providers run with the agent's private `workspace` as their current
  directory by default
- each session stores an immutable-by-convention snapshot of the agent contract
- each agent has separate `inbox`, `outbox`, and `workspace` directories

Logical isolation:

- each agent receives a prompt containing only its own agent package
- each agent receives a `context.json` contract listing only authorized shared
  files, project files, and prior handoff files routed into its own inbox
- process providers receive a minimal environment by default
- session state is persisted in `state.json`

## Shared areas

Shared files live under `.at/shared`:

- `memory`: long-lived notes and decisions
- `skills`: reusable instructions, recipes, and tool notes
- `policies`: context and memory governance rules
- `docs`: shared reference documents selected into context by AT
- `inbox`: cross-session scratchpad and incoming material

Shared projects live under `.at/projects` by default, but a session can point to
any project path.

## State machine

Each step has one of these statuses:

- `queued`
- `running`
- `done`
- `failed`

A session can be resumed after interruption. A lock file prevents two runners
from advancing the same session at the same time.

## Runtime Nodes

AT advances each step through platform-controlled nodes:

1. `prepare_agent`: create physical directories and materialize contracts.
2. `route_prior_handoff`: copy prior artifacts into the current inbox.
3. `build_context`: write the agent-specific `context.json` contract.
4. `run_agent`: execute the configured provider from the private workspace.
5. `collect_output`: ensure `outbox/artifact.md` exists.
6. `collect_memory_proposals`: copy proposed memory updates to the session.
7. `audit_permissions`: compare protected path snapshots with permissions.
8. `route_handoff`: copy the current artifact to `handoff` and the next inbox.
9. `update_state`: persist the result.

Agents do not directly advance the state machine or copy files into another
agent's directory.

## Permission Audit

The first audit layer is path based. It compares snapshots before and after a
provider run for:

- `.at/shared`
- the shared project path
- other agent directories
- `state.json`
- `handoff`

By default, only `code` may write the shared project. No agent may directly write
shared memory, skills, policies, another agent's files, or session control
files.

## Process Sandbox

The default process provider environment is minimal. AT passes the current
agent's own directories, contract files, and only the shared/project paths granted
by `permissions.json`.

Default AT variables:

- `AT_SESSION_ID`
- `AT_AGENT`
- `AT_AGENT_DIR`
- `AT_INBOX`
- `AT_OUTBOX`
- `AT_AGENT_WORKSPACE`
- `AT_PERMISSIONS`
- `AT_OUTPUT_CONTRACT`
- `AT_CONTEXT`
- `AT_SHARED_MEMORY`, `AT_SHARED_SKILLS`, and `AT_SHARED_INBOX` when readable
- `AT_PROJECT_PATH` when project access is granted

AT does not pass workspace root, shared root, or session root in the default
process sandbox. A provider can opt into `env_policy: "inherit"` when required,
but that should be treated as a larger trust boundary.

## Provider adapter

The provider boundary is deliberately narrow:

- AT builds a complete prompt for one agent step.
- A provider returns text output.
- AT writes that output as the step artifact and advances the state machine.

This makes Codex, opencode, and other CLIs interchangeable as long as they can
accept a prompt through stdin, an argument, or a prompt file.

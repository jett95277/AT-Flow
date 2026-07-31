from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_AGENT_PROFILES: dict[str, str] = {
    "main": """# main agent

## Mission

Own the conversation-level task contract. Convert the user's request into a
clear AT session brief, keep the work aligned with the user's intent, and decide
when a handoff is ready for the next agent.

## Owns

- User intent, constraints, and success criteria.
- Task framing, scope boundaries, and priority.
- Clarifying questions when the request is too ambiguous or risky.
- Acceptance criteria that later agents can verify.
- Final handoff shape for the analysis agent.

## Boundaries

- Do not implement code changes.
- Do not run verification as a substitute for the test agent.
- Do not make architecture commitments that require code-level inspection unless
  the evidence is already available.
- Do not modify shared memory, skills, or project files unless the user asks for
  governance or workflow changes.
- Do not skip ambiguity that would make downstream work unsafe.

## Inputs

- The original user task.
- Shared memory, skills, and inbox paths.
- Existing session state and any prior artifacts.

## Output Contract

Write a concise handoff containing:

- task summary
- explicit goal
- non-goals
- constraints
- acceptance criteria
- risks or questions that must be resolved before implementation
- recommended next action for `analysis`
""",
    "analysis": """# analysis agent

## Mission

Turn the main agent's task contract into an execution plan. Identify the safest
path through the codebase or project, explain tradeoffs, and prepare the code
agent for a focused implementation pass.

## Owns

- Problem decomposition.
- Architecture and workflow analysis.
- Dependency, file, and interface discovery.
- Risk assessment and mitigation plan.
- Test strategy for the test agent.
- Handoff instructions for the code agent.

## Boundaries

- Do not edit production code.
- Do not perform broad refactors.
- Do not claim verification is complete.
- Do not override the main agent's task scope without recording the reason.
- Do not use hidden assumptions when a project fact can be inspected.

## Inputs

- Main agent artifact.
- Shared memory and skills.
- Project files that need inspection.
- Existing conventions in the shared project.

## Output Contract

Write a plan containing:

- relevant project facts
- proposed approach
- files or areas likely to change
- implementation steps for `code`
- expected verification steps for `test`
- known risks, edge cases, and unresolved questions
""",
    "code": """# code agent

## Mission

Make the smallest coherent implementation that satisfies the task contract and
analysis plan. Preserve project conventions and leave clear artifacts for the
test agent.

## Owns

- Source edits in the shared project.
- Local implementation decisions inside the agreed scope.
- Dependency-free fixes when possible.
- Recording changed files and important reasoning.
- Handoff notes describing what needs verification.

## Boundaries

- Do not expand scope beyond the main and analysis artifacts.
- Do not perform unrelated refactors or formatting churn.
- Do not modify another agent's artifact except by writing a new handoff.
- Do not change shared memory or skills unless the task is explicitly about
  platform governance.
- Do not claim the work is verified; leave that judgment to `test`.
- Do not use destructive project operations without explicit approval.

## Inputs

- Main and analysis artifacts.
- Shared skills that apply to implementation.
- The shared project path.
- Existing tests and project conventions.

## Output Contract

Write an implementation handoff containing:

- changed files
- behavioral changes
- assumptions made
- commands run, if any
- risks left for `test`
- exact verification suggestions
""",
    "test": """# test agent

## Mission

Verify the completed implementation against the acceptance criteria. Produce a
clear pass/fail report with evidence and route failures back to the appropriate
agent.

## Owns

- Running or designing verification steps.
- Inspecting implementation artifacts and changed files.
- Comparing results with acceptance criteria.
- Recording evidence, failures, and residual risk.
- Recommending whether the session is complete or needs another pass.

## Boundaries

- Do not implement production fixes.
- Do not silently change the acceptance criteria.
- Do not mark work as complete without evidence.
- Do not hide failed or skipped checks.
- Do not edit shared memory or skills unless the user requested a process
  update.
- Only create or modify test fixtures when the verification plan explicitly
  requires it, and record those changes.

## Inputs

- Main, analysis, and code artifacts.
- Acceptance criteria and verification plan.
- Shared project path.
- Available test commands and project documentation.

## Output Contract

Write a verification report containing:

- checks performed
- pass/fail result
- command output summary
- defects found
- skipped checks and why
- residual risk
- recommended next state: complete, retry code, retry analysis, or ask user
""",
}


DEFAULT_AGENT_OUTPUTS: dict[str, str] = {
    "main": """# main output contract

Write `outbox/artifact.md` with these sections:

- Task Summary
- Goal
- Non-Goals
- Constraints
- Acceptance Criteria
- Risks And Questions
- Handoff To Analysis
""",
    "analysis": """# analysis output contract

Write `outbox/artifact.md` with these sections:

- Relevant Project Facts
- Proposed Approach
- Files Or Areas To Inspect Or Change
- Implementation Steps For Code
- Verification Plan For Test
- Risks And Open Questions
""",
    "code": """# code output contract

Write `outbox/artifact.md` with these sections:

- Changed Files
- Behavioral Changes
- Assumptions
- Commands Run
- Risks Left For Test
- Verification Suggestions
""",
    "test": """# test output contract

Write `outbox/artifact.md` with these sections:

- Checks Performed
- Result
- Command Output Summary
- Defects Found
- Skipped Checks
- Residual Risk
- Recommended Next State
""",
}


DEFAULT_AGENT_PERMISSIONS: dict[str, dict[str, Any]] = {
    "main": {
        "version": 1,
        "read": {
            "shared_memory": True,
            "shared_skills": True,
            "shared_inbox": True,
            "project": False,
            "inbox": True,
        },
        "write": {
            "agent_workspace": True,
            "agent_outbox": True,
            "project": False,
            "shared": False,
            "other_agents": False,
            "session_control": False,
            "proposals": True,
        },
        "audit": {
            "fail_on_project_change": True,
            "fail_on_shared_change": True,
            "fail_on_other_agent_change": True,
            "fail_on_session_control_change": True,
        },
    },
    "analysis": {
        "version": 1,
        "read": {
            "shared_memory": True,
            "shared_skills": True,
            "shared_inbox": True,
            "project": True,
            "inbox": True,
        },
        "write": {
            "agent_workspace": True,
            "agent_outbox": True,
            "project": False,
            "shared": False,
            "other_agents": False,
            "session_control": False,
            "proposals": True,
        },
        "audit": {
            "fail_on_project_change": True,
            "fail_on_shared_change": True,
            "fail_on_other_agent_change": True,
            "fail_on_session_control_change": True,
        },
    },
    "code": {
        "version": 1,
        "read": {
            "shared_memory": True,
            "shared_skills": True,
            "shared_inbox": True,
            "project": True,
            "inbox": True,
        },
        "write": {
            "agent_workspace": True,
            "agent_outbox": True,
            "project": True,
            "shared": False,
            "other_agents": False,
            "session_control": False,
            "proposals": True,
        },
        "audit": {
            "fail_on_project_change": False,
            "fail_on_shared_change": True,
            "fail_on_other_agent_change": True,
            "fail_on_session_control_change": True,
        },
    },
    "test": {
        "version": 1,
        "read": {
            "shared_memory": True,
            "shared_skills": True,
            "shared_inbox": True,
            "project": True,
            "inbox": True,
        },
        "write": {
            "agent_workspace": True,
            "agent_outbox": True,
            "project": False,
            "shared": False,
            "other_agents": False,
            "session_control": False,
            "proposals": True,
        },
        "audit": {
            "fail_on_project_change": True,
            "fail_on_shared_change": True,
            "fail_on_other_agent_change": True,
            "fail_on_session_control_change": True,
        },
    },
}


def default_agent_profile(agent: str) -> str:
    return DEFAULT_AGENT_PROFILES.get(
        agent,
        f"""# {agent} agent

## Mission

Complete the `{agent}` step while staying inside the explicit AT session scope.

## Boundaries

- Use only explicit shared paths and prior artifacts.
- Write a concise handoff for the next step.
- Record uncertainty instead of inventing facts.
""",
    )


def default_agent_output(agent: str) -> str:
    return DEFAULT_AGENT_OUTPUTS.get(
        agent,
        f"""# {agent} output contract

Write `outbox/artifact.md` with a concise summary, evidence, and handoff notes.
""",
    )


def default_agent_permissions(agent: str) -> dict[str, Any]:
    default = {
        "version": 1,
        "read": {
            "shared_memory": True,
            "shared_skills": True,
            "shared_inbox": True,
            "project": False,
            "inbox": True,
        },
        "write": {
            "agent_workspace": True,
            "agent_outbox": True,
            "project": False,
            "shared": False,
            "other_agents": False,
            "session_control": False,
            "proposals": True,
        },
        "audit": {
            "fail_on_project_change": True,
            "fail_on_shared_change": True,
            "fail_on_other_agent_change": True,
            "fail_on_session_control_change": True,
        },
    }
    return deepcopy(DEFAULT_AGENT_PERMISSIONS.get(agent, default))

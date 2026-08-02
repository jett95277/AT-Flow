import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CodeAgentPanel } from "./CodeAgentPanel";
import type { ProviderCapability, ProviderStatus, SessionState } from "../api/types";

describe("CodeAgentPanel", () => {
  it("shows the selected and resolved CodeAgent state", () => {
    render(
      <CodeAgentPanel
        activeSession={session("s1", "auto")}
        providers={providers()}
        providerStatus={status()}
        busy={false}
        onSwitchProvider={vi.fn()}
      />
    );

    expect(screen.getByRole("region", { name: "CodeAgent 切换" })).toBeInTheDocument();
    expect(screen.getByLabelText("选择 CodeAgent")).toHaveValue("auto");
    expect(screen.getByText("当前 CodeAgent")).toBeInTheDocument();
    expect(screen.getByText("解析 Provider")).toBeInTheDocument();
    expect(screen.getAllByText("codex").length).toBeGreaterThan(0);
    expect(screen.getByText("下一 Agent")).toBeInTheDocument();
    expect(screen.getByText("code")).toBeInTheDocument();
    expect(screen.getByText("command not found: codex")).toBeInTheDocument();
  });

  it("calls the switch callback when the selector changes", () => {
    const onSwitchProvider = vi.fn();

    render(
      <CodeAgentPanel
        activeSession={session("s1", "mock")}
        providers={providers()}
        providerStatus={{ ...status(), selected_provider: "mock", resolved_provider: "mock", available: true }}
        busy={false}
        onSwitchProvider={onSwitchProvider}
      />
    );

    fireEvent.change(screen.getByLabelText("选择 CodeAgent"), { target: { value: "opencode" } });

    expect(onSwitchProvider).toHaveBeenCalledWith("opencode");
  });

  it("locks provider switching while a session step is running", () => {
    const running = session("s1", "mock");
    running.status = "running";
    running.steps[0].status = "running";

    render(
      <CodeAgentPanel
        activeSession={running}
        providers={providers()}
        providerStatus={{ ...status(), selected_provider: "mock", resolved_provider: "mock", available: true }}
        busy={false}
        onSwitchProvider={vi.fn()}
      />
    );

    expect(screen.getByLabelText("选择 CodeAgent")).toBeDisabled();
  });

  it("locks provider switching while a mutation is pending", () => {
    render(
      <CodeAgentPanel
        activeSession={session("s1", "mock")}
        providers={providers()}
        providerStatus={status()}
        busy
        onSwitchProvider={vi.fn()}
      />
    );

    expect(screen.getByLabelText("选择 CodeAgent")).toBeDisabled();
  });
});

function providers(): ProviderCapability[] {
  return [
    { name: "auto", available: true, provider_type: "routing", detail: "routes by agent" },
    { name: "mock", available: true, provider_type: "mock", detail: "mock provider is always available" },
    { name: "codex", available: false, provider_type: "process", detail: "command not found: codex" },
    { name: "opencode", available: false, provider_type: "process", detail: "command not found: opencode" }
  ];
}

function status(): ProviderStatus {
  return {
    selected_provider: "auto",
    next_agent: "code",
    resolved_provider: "codex",
    available: false,
    detail: "command not found: codex"
  };
}

function session(id: string, provider: string): SessionState {
  return {
    schema_version: 1,
    id,
    task: "demo",
    project_path: "project",
    provider,
    created_at: "now",
    updated_at: "now",
    status: "queued",
    current_stage: "code",
    failure_reason: null,
    steps: [
      {
        agent: "code",
        status: "queued",
        started_at: null,
        finished_at: null,
        artifact_path: null,
        error: null,
        failure_reason: null,
        retry_count: 0,
        max_retries: 1,
        retryable: true,
        input_paths: []
      }
    ]
  };
}

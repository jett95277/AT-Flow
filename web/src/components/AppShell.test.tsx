import "@testing-library/jest-dom/vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";
import { AtApiError, type AtApiClient } from "../api/client";
import type { SessionState } from "../api/types";

describe("AppShell", () => {
  it("renders the three console regions", async () => {
    render(<AppShell client={fakeClient()} />);

    expect(await screen.findByRole("banner")).toHaveTextContent("AT Flow 控制台");
    expect(screen.getByRole("region", { name: "会话列表" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "文档查看器" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "运行时检查器" })).toBeInTheDocument();
  });

  it("marks all three console panels as independent scroll regions", async () => {
    const { container } = render(<AppShell client={fakeClient()} />);

    await screen.findByRole("banner");

    expect(container.querySelectorAll("[data-scroll-region]")).toHaveLength(3);
  });

  it("changes the active session from the session list", async () => {
    const first = session("s1", "done", "test");
    const second = session("s2", "queued", "main");
    const client = fakeClient([first, second]);

    render(<AppShell client={client} />);

    const secondSession = await screen.findByRole("button", { name: /s2/ });
    fireEvent.click(secondSession);

    expect(secondSession).toHaveAttribute("aria-current", "true");
    expect(within(screen.getByRole("region", { name: "CodeAgent 切换" })).getByText("s2")).toBeInTheDocument();
    await waitFor(() => expect(client.getTrace).toHaveBeenCalledWith("s2"));
    await waitFor(() => expect(client.getAudit).toHaveBeenCalledWith("s2"));
    await waitFor(() => expect(client.getProviderStatus).toHaveBeenCalledWith("s2"));
  });

  it("renders the structured Chinese display artifact for a completed session", async () => {
    const done = session("s1", "done", "main");
    done.steps[0].artifact_path = "artifact.md";
    const client = fakeClient([done]);
    client.getArtifact = vi.fn().mockResolvedValue({
      source: "## Task Summary",
      display: "## 任务摘要",
      source_language: "en",
      display_language: "zh",
      display_status: "completed",
      display_provider: "codex",
      display_error: null
    });

    render(<AppShell client={client} />);

    expect(await screen.findByText("## 任务摘要")).toBeInTheDocument();
    expect(client.getArtifact).toHaveBeenCalledWith("s1", "main");
  });

  it("ignores evidence responses from a previously selected session", async () => {
    const first = session("s1", "done", "test");
    const second = session("s2", "queued", "main");
    const client = fakeClient([first, second]);
    let resolveFirstTrace: ((value: { trace: Array<{ event: string }> }) => void) | undefined;
    const firstTrace = new Promise<{ trace: Array<{ event: string }> }>((resolve) => {
      resolveFirstTrace = resolve;
    });
    client.getTrace = vi.fn().mockImplementation((id: string) =>
      id === "s1" ? firstTrace : Promise.resolve({ trace: [{ event: "s2-event" }] })
    );

    render(<AppShell client={client} />);

    fireEvent.click(await screen.findByRole("button", { name: /s2/ }));
    expect(await screen.findByText("s2-event")).toBeInTheDocument();

    await act(async () => {
      resolveFirstTrace?.({ trace: [{ event: "s1-event" }] });
      await firstTrace;
    });

    expect(screen.queryByText("s1-event")).not.toBeInTheDocument();
    expect(screen.getByText("s2-event")).toBeInTheDocument();
  });

  it("creates a session from the entered task and initial CodeAgent", async () => {
    const client = fakeClient();

    render(<AppShell client={client} />);

    fireEvent.change(await screen.findByLabelText("任务"), { target: { value: "实现真实任务" } });
    fireEvent.change(screen.getByLabelText("初始 CodeAgent"), { target: { value: "auto" } });
    fireEvent.click(screen.getByRole("button", { name: "创建会话" }));

    await waitFor(() =>
      expect(client.createSession).toHaveBeenCalledWith({ task: "实现真实任务", provider: "auto" })
    );
  });

  it("preserves typed API error details in runtime evidence", async () => {
    const queued = session("s1", "queued", "main");
    const client = fakeClient([queued]);
    client.runOneStep = vi.fn().mockRejectedValue(
      new AtApiError(409, { code: "invalid_transition", message: "blocked", retryable: true })
    );

    render(<AppShell client={client} />);

    fireEvent.click(await screen.findByRole("button", { name: "执行一步" }));

    const evidence = within(screen.getByRole("region", { name: "运行证据" }));
    expect(await evidence.findByText("invalid_transition")).toBeInTheDocument();
    expect(evidence.getByText("blocked")).toBeInTheDocument();
    expect(evidence.getByText("可重试")).toBeInTheDocument();
  });

  it("clears a previous command error when the next command succeeds", async () => {
    const queued = session("s1", "queued", "main");
    const client = fakeClient([queued]);
    client.runOneStep = vi
      .fn()
      .mockRejectedValueOnce(new AtApiError(409, { code: "invalid_transition", message: "blocked", retryable: true }))
      .mockResolvedValueOnce({ session: queued });

    render(<AppShell client={client} />);

    const runButton = await screen.findByRole("button", { name: "执行一步" });
    fireEvent.click(runButton);
    expect(await screen.findByText("invalid_transition")).toBeInTheDocument();

    await waitFor(() => expect(runButton).toBeEnabled());
    fireEvent.click(runButton);

    await waitFor(() => expect(screen.queryByText("invalid_transition")).not.toBeInTheDocument());
  });
});

function fakeClient(sessions: SessionState[] = []): AtApiClient {
  return {
    getHealth: vi.fn().mockResolvedValue({ status: "ok", workspace: "demo" }),
    getDoctor: vi.fn().mockResolvedValue({ checks: [] }),
    getProviders: vi.fn().mockResolvedValue({ providers: [] }),
    getProviderStatus: vi.fn().mockResolvedValue({
      selected_provider: "mock",
      next_agent: "main",
      resolved_provider: "mock",
      available: true,
      detail: "available"
    }),
    updateProvider: vi.fn().mockResolvedValue({}),
    getSessions: vi.fn().mockResolvedValue({ sessions }),
    getWorkspaceTree: vi.fn().mockResolvedValue({ tree: [] }),
    getFile: vi.fn(),
    getState: vi.fn().mockImplementation((id: string) => Promise.resolve(sessions.find((item) => item.id === id))),
    getTrace: vi.fn().mockResolvedValue({ trace: [] }),
    getAudit: vi.fn().mockResolvedValue({ audit: [] }),
    getLanguage: vi.fn().mockResolvedValue({
      schema_version: 2,
      source_language: "zh",
      runtime_language: "en",
      display_language: "zh",
      artifact_mode: "bilingual",
      task_original: "任务",
      task_runtime: "Task",
      input_translation: { status: "completed", provider: "codex", error: null, updated_at: "now" },
      display_translation: { status: "pending", provider: "codex", error: null, updated_at: "now" }
    }),
    getArtifact: vi.fn().mockResolvedValue({
      source: "artifact",
      display: null,
      source_language: "en",
      display_language: "zh",
      display_status: "pending",
      display_provider: "codex",
      display_error: null
    }),
    createSession: vi.fn().mockResolvedValue({}),
    runOneStep: vi.fn().mockResolvedValue({}),
    continueSession: vi.fn().mockResolvedValue({}),
    retrySession: vi.fn().mockResolvedValue({})
  } as unknown as AtApiClient;
}

function session(id: string, status: string, currentStage: string): SessionState {
  return {
    schema_version: 1,
    id,
    task: "demo",
    project_path: "project",
    provider: "mock",
    created_at: "2026-08-02T09:00:00Z",
    updated_at: "2026-08-02T09:01:00Z",
    status,
    current_stage: currentStage,
    failure_reason: null,
    steps: [
      {
        agent: currentStage,
        status,
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

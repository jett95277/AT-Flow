import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { SessionState } from "../api/types";
import { RunControls } from "./RunControls";

describe("RunControls", () => {
  it("calls runtime action callbacks", () => {
    const actions = actionsMock();

    render(
      <RunControls
        activeSession={session("queued")}
        busy={false}
        task="demo"
        initialProvider="mock"
        providerOptions={["mock", "auto", "codex", "opencode"]}
        {...actions}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "创建会话" }));
    fireEvent.click(screen.getByRole("button", { name: "执行一步" }));
    fireEvent.click(screen.getByRole("button", { name: "继续运行" }));
    fireEvent.click(screen.getByRole("button", { name: "刷新诊断" }));

    expect(actions.onCreateSession).toHaveBeenCalledTimes(1);
    expect(actions.onRunOneStep).toHaveBeenCalledWith("s1");
    expect(actions.onContinue).toHaveBeenCalledWith("s1");
    expect(actions.onRetry).not.toHaveBeenCalled();
    expect(actions.onRefreshDoctor).toHaveBeenCalledTimes(1);
  });

  it("lets the user select the initial CodeAgent for a new session", () => {
    const actions = actionsMock();

    render(
      <RunControls
        activeSession={session("queued")}
        busy={false}
        task="demo"
        initialProvider="mock"
        providerOptions={["mock", "auto", "codex", "opencode"]}
        {...actions}
      />
    );

    fireEvent.change(screen.getByLabelText("初始 CodeAgent"), { target: { value: "codex" } });

    expect(actions.onInitialProviderChange).toHaveBeenCalledWith("codex");
  });

  it("offers explicit auto routing without changing the initial mock mode", () => {
    const actions = actionsMock();

    render(
      <RunControls
        activeSession={session("queued")}
        busy={false}
        task="demo"
        initialProvider="mock"
        providerOptions={["mock", "auto", "codex", "opencode"]}
        {...actions}
      />
    );

    expect(screen.getByLabelText("初始 CodeAgent")).toHaveValue("mock");
    expect(screen.getByRole("option", { name: "mock" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "auto" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "codex" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "opencode" })).toBeInTheDocument();
  });

  it("requires a non-empty task before creating a session", () => {
    const actions = actionsMock();
    const props = {
      activeSession: null,
      busy: false,
      initialProvider: "mock",
      providerOptions: ["mock", "auto"],
      ...actions
    };
    const { rerender } = render(<RunControls {...props} task="   " />);

    expect(screen.getByLabelText("任务")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "创建会话" })).toBeDisabled();

    rerender(<RunControls {...props} task="实现真实任务" />);

    expect(screen.getByRole("button", { name: "创建会话" })).toBeEnabled();
  });

  it("reports task edits", () => {
    const actions = actionsMock();
    render(
      <RunControls
        activeSession={null}
        busy={false}
        task=""
        initialProvider="mock"
        providerOptions={["mock"]}
        {...actions}
      />
    );

    fireEvent.change(screen.getByLabelText("任务"), { target: { value: "新任务" } });

    expect(actions.onTaskChange).toHaveBeenCalledWith("新任务");
  });

  it("enables only actions allowed by the active session state", () => {
    const actions = actionsMock();
    const baseProps = {
      busy: false,
      task: "demo",
      initialProvider: "mock",
      providerOptions: ["mock"],
      ...actions
    };
    const { rerender } = render(<RunControls {...baseProps} activeSession={session("queued")} />);

    expect(screen.getByRole("button", { name: "执行一步" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "继续运行" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "重试" })).toBeDisabled();

    rerender(<RunControls {...baseProps} activeSession={session("running")} />);
    expect(screen.getByRole("button", { name: "执行一步" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "继续运行" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "重试" })).toBeDisabled();

    rerender(<RunControls {...baseProps} activeSession={session("done")} />);
    expect(screen.getByRole("button", { name: "执行一步" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "继续运行" })).toBeDisabled();

    rerender(<RunControls {...baseProps} activeSession={session("aborted")} />);
    expect(screen.getByRole("button", { name: "执行一步" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "继续运行" })).toBeDisabled();

    rerender(<RunControls {...baseProps} activeSession={session("failed")} />);
    expect(screen.getByRole("button", { name: "执行一步" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "继续运行" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "重试" })).toBeEnabled();
  });

  it("disables exhausted retries and all mutations while busy", () => {
    const actions = actionsMock();
    const props = {
      task: "demo",
      initialProvider: "mock",
      providerOptions: ["mock"],
      ...actions
    };
    const { rerender } = render(
      <RunControls {...props} activeSession={session("failed", 1, 1)} busy={false} />
    );

    expect(screen.getByRole("button", { name: "重试" })).toBeDisabled();

    rerender(<RunControls {...props} activeSession={session("queued")} busy />);
    expect(screen.getByRole("button", { name: "创建会话" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "执行一步" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "继续运行" })).toBeDisabled();
  });

  it("retries the active failed session", () => {
    const actions = actionsMock();
    render(
      <RunControls
        activeSession={session("failed")}
        busy={false}
        task="demo"
        initialProvider="mock"
        providerOptions={["mock"]}
        {...actions}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "重试" }));

    expect(actions.onRetry).toHaveBeenCalledWith("s1");
  });
});

function actionsMock() {
  return {
    onCreateSession: vi.fn(),
    onRunOneStep: vi.fn(),
    onContinue: vi.fn(),
    onRetry: vi.fn(),
    onRefreshDoctor: vi.fn(),
    onTaskChange: vi.fn(),
    onInitialProviderChange: vi.fn()
  };
}

function session(status: string, retryCount = 0, maxRetries = 1): SessionState {
  return {
    schema_version: 1,
    id: "s1",
    task: "demo",
    project_path: "project",
    provider: "mock",
    created_at: "now",
    updated_at: "now",
    status,
    current_stage: "main",
    failure_reason: status === "failed" ? "failed" : null,
    steps: [
      {
        agent: "main",
        status,
        started_at: null,
        finished_at: null,
        artifact_path: null,
        error: status === "failed" ? "failed" : null,
        failure_reason: status === "failed" ? "failed" : null,
        retry_count: retryCount,
        max_retries: maxRetries,
        retryable: status === "failed",
        input_paths: []
      },
      ...(status === "failed" || status === "aborted"
        ? [
            {
              agent: "analysis",
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
        : [])
    ]
  };
}

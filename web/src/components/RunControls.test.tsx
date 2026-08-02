import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RunControls } from "./RunControls";

describe("RunControls", () => {
  it("calls runtime action callbacks", () => {
    const actions = actionsMock();

    render(<RunControls activeSessionId="s1" selectedProvider="mock" {...actions} />);

    fireEvent.click(screen.getByRole("button", { name: "创建会话" }));
    fireEvent.click(screen.getByRole("button", { name: "执行一步" }));
    fireEvent.click(screen.getByRole("button", { name: "继续运行" }));
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    fireEvent.click(screen.getByRole("button", { name: "刷新诊断" }));

    expect(actions.onCreateSession).toHaveBeenCalledTimes(1);
    expect(actions.onRunOneStep).toHaveBeenCalledWith("s1");
    expect(actions.onContinue).toHaveBeenCalledWith("s1");
    expect(actions.onRetry).toHaveBeenCalledWith("s1");
    expect(actions.onRefreshDoctor).toHaveBeenCalledTimes(1);
  });

  it("lets the user select a provider", () => {
    const actions = actionsMock();

    render(<RunControls activeSessionId="s1" selectedProvider="mock" {...actions} />);

    fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "codex" } });

    expect(actions.onProviderChange).toHaveBeenCalledWith("codex");
  });

  it("offers explicit auto routing without changing the default mock mode", () => {
    const actions = actionsMock();

    render(<RunControls activeSessionId="s1" selectedProvider="mock" {...actions} />);

    expect(screen.getByLabelText("Provider")).toHaveValue("mock");
    expect(screen.getByRole("option", { name: "mock" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "auto" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "codex" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "opencode" })).toBeInTheDocument();
  });
});

function actionsMock() {
  return {
    onCreateSession: vi.fn(),
    onRunOneStep: vi.fn(),
    onContinue: vi.fn(),
    onRetry: vi.fn(),
    onRefreshDoctor: vi.fn(),
    onProviderChange: vi.fn()
  };
}

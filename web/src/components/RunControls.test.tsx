import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RunControls } from "./RunControls";

describe("RunControls", () => {
  it("calls runtime action callbacks", () => {
    const actions = {
      onCreateSession: vi.fn(),
      onRunOneStep: vi.fn(),
      onContinue: vi.fn(),
      onRetry: vi.fn(),
      onRefreshDoctor: vi.fn()
    };

    render(<RunControls activeSessionId="s1" {...actions} />);

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
});

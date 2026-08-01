import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StateMachine } from "./StateMachine";
import type { SessionState } from "../api/types";

describe("StateMachine", () => {
  it("renders session status and all agent step statuses", () => {
    render(<StateMachine session={sessionState()} />);

    expect(screen.getByText("会话状态：运行中")).toBeInTheDocument();
    expect(screen.getByText("main")).toBeInTheDocument();
    expect(screen.getByText("已完成")).toBeInTheDocument();
    expect(screen.getByText("analysis")).toBeInTheDocument();
    expect(screen.getByText("运行中")).toBeInTheDocument();
    expect(screen.getByText("code")).toBeInTheDocument();
    expect(screen.getAllByText("排队中")).toHaveLength(2);
    expect(screen.getByText("test")).toBeInTheDocument();
  });
});

function sessionState(): SessionState {
  return {
    schema_version: 1,
    id: "s1",
    task: "demo",
    project_path: "project",
    provider: "mock",
    created_at: "now",
    updated_at: "now",
    status: "running",
    current_stage: "analysis",
    failure_reason: null,
    steps: ["main", "analysis", "code", "test"].map((agent, index) => ({
      agent,
      status: index === 0 ? "done" : index === 1 ? "running" : "queued",
      started_at: null,
      finished_at: null,
      artifact_path: null,
      error: null,
      failure_reason: null,
      retry_count: 0,
      max_retries: 1,
      retryable: true,
      input_paths: []
    }))
  };
}

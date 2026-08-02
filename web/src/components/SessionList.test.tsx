import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { SessionState } from "../api/types";
import { SessionList } from "./SessionList";

describe("SessionList", () => {
  it("selects a session from the list", () => {
    const onSelect = vi.fn();
    const first = session("s1", "queued");

    render(<SessionList sessions={[first]} activeSessionId={null} onSelect={onSelect} />);

    fireEvent.click(screen.getByRole("button", { name: /s1/ }));

    expect(onSelect).toHaveBeenCalledWith(first);
  });

  it("marks the active session", () => {
    render(<SessionList sessions={[session("s1", "running")]} activeSessionId="s1" onSelect={vi.fn()} />);

    expect(screen.getByRole("button", { name: /s1/ })).toHaveAttribute("aria-current", "true");
  });
});

function session(id: string, status: string): SessionState {
  return {
    schema_version: 1,
    id,
    task: "demo",
    project_path: "project",
    provider: "mock",
    created_at: "2026-08-02T09:00:00Z",
    updated_at: "2026-08-02T09:01:00Z",
    status,
    current_stage: "main",
    failure_reason: null,
    steps: [
      {
        agent: "main",
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

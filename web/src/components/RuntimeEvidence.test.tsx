import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RuntimeEvidence } from "./RuntimeEvidence";

describe("RuntimeEvidence", () => {
  it("renders trace, audit, artifact, and typed error evidence", () => {
    render(
      <RuntimeEvidence
        trace={[{ event: "collect_output", agent: "main", status: "running" }]}
        audit={[{ file: "00-main.json", agent: "main", violations: [] }]}
        doctor={[]}
        artifact={{
          source: "## Task Summary",
          display: "## 任务摘要",
          source_language: "en",
          display_language: "zh",
          display_status: "completed",
          display_provider: "codex",
          display_error: null
        }}
        error={{ code: "file_not_allowed", message: "blocked", retryable: false }}
      />
    );

    expect(screen.getByText("collect_output")).toBeInTheDocument();
    expect(screen.getByText("00-main.json")).toBeInTheDocument();
    expect(screen.getByText("## 任务摘要")).toBeInTheDocument();
    expect(screen.getByText("英文源产物")).toBeInTheDocument();
    expect(screen.getByText("file_not_allowed")).toBeInTheDocument();
  });

  it("does not silently present English as Chinese when display translation fails", () => {
    render(
      <RuntimeEvidence
        trace={[]}
        audit={[]}
        doctor={[]}
        artifact={{
          source: "## Task Summary",
          display: null,
          source_language: "en",
          display_language: "zh",
          display_status: "failed",
          display_provider: "codex",
          display_error: "translator offline"
        }}
        error={null}
      />
    );

    expect(screen.getByText("中文展示生成失败")).toBeInTheDocument();
    expect(screen.getByText("translator offline")).toBeInTheDocument();
    const source = screen.getByText("英文源产物").closest("details");
    expect(source).not.toHaveAttribute("open");
    expect(screen.queryByText("## Task Summary")).toBeInTheDocument();
  });

  it("renders provider capability doctor checks", () => {
    render(
      <RuntimeEvidence
        trace={[]}
        audit={[]}
        doctor={[{ name: "provider:codex", ok: false, detail: "command not found: codex" }]}
        artifact={null}
        error={null}
      />
    );

    expect(screen.getByText("provider:codex")).toBeInTheDocument();
    expect(screen.getByText("FAIL")).toBeInTheDocument();
    expect(screen.getByText("command not found: codex")).toBeInTheDocument();
  });
});

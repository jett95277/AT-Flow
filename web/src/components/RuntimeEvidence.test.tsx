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
        artifact="## Task Summary"
        error={{ code: "file_not_allowed", message: "blocked", retryable: false }}
      />
    );

    expect(screen.getByText("collect_output")).toBeInTheDocument();
    expect(screen.getByText("00-main.json")).toBeInTheDocument();
    expect(screen.getByText("## Task Summary")).toBeInTheDocument();
    expect(screen.getByText("file_not_allowed")).toBeInTheDocument();
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

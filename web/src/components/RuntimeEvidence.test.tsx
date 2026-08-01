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
        artifact="## Task Summary"
        error={{ code: "file_not_allowed", message: "blocked", retryable: false }}
      />
    );

    expect(screen.getByText("collect_output")).toBeInTheDocument();
    expect(screen.getByText("00-main.json")).toBeInTheDocument();
    expect(screen.getByText("## Task Summary")).toBeInTheDocument();
    expect(screen.getByText("file_not_allowed")).toBeInTheDocument();
  });
});

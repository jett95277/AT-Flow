import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceTree } from "./WorkspaceTree";
import type { FileNode } from "../api/types";

describe("WorkspaceTree", () => {
  it("expands directories and selects files", async () => {
    const onSelect = vi.fn();
    const tree: FileNode[] = [
      {
        name: "agents",
        path: "agents",
        kind: "directory",
        children: [
          {
            name: "main",
            path: "agents/main",
            kind: "directory",
            children: [{ name: "agent.md", path: "agents/main/agent.md", kind: "file", children: [] }]
          }
        ]
      }
    ];

    render(<WorkspaceTree tree={tree} selectedPath={null} onSelect={onSelect} />);

    fireEvent.click(screen.getByRole("button", { name: "agents" }));
    fireEvent.click(screen.getByRole("button", { name: "main" }));
    fireEvent.click(screen.getByRole("button", { name: "agent.md" }));

    expect(onSelect).toHaveBeenCalledWith("agents/main/agent.md");
  });
});

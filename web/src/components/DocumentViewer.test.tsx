import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocumentViewer } from "./DocumentViewer";

describe("DocumentViewer", () => {
  it("renders selected document content without editing controls", () => {
    render(<DocumentViewer path="agents/main/agent.md" content={"# Main Agent\n\nRead only."} loading={false} />);

    const viewer = screen.getByRole("region", { name: "文档查看器" });
    expect(viewer).toHaveTextContent("agents/main/agent.md");
    expect(viewer).toHaveTextContent("# Main Agent");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("renders empty state when no document is selected", () => {
    render(<DocumentViewer path={null} content={null} loading={false} />);

    expect(screen.getByText("请选择一个工作区文件")).toBeInTheDocument();
  });
});

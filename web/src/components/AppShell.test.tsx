import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";
import type { AtApiClient } from "../api/client";

describe("AppShell", () => {
  it("renders the three console regions", async () => {
    render(<AppShell client={fakeClient()} />);

    expect(await screen.findByRole("banner")).toHaveTextContent("AT Flow 控制台");
    expect(screen.getByRole("region", { name: "会话列表" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "文档查看器" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "运行时检查器" })).toBeInTheDocument();
  });
});

function fakeClient(): AtApiClient {
  return {
    getHealth: vi.fn().mockResolvedValue({ status: "ok", workspace: "demo" }),
    getDoctor: vi.fn().mockResolvedValue({ checks: [] }),
    getSessions: vi.fn().mockResolvedValue({ sessions: [] }),
    getWorkspaceTree: vi.fn().mockResolvedValue({ tree: [] }),
    getFile: vi.fn()
  } as unknown as AtApiClient;
}

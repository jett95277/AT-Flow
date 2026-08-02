import { describe, expect, it, vi } from "vitest";

import { AtApiClient } from "./client";

describe("AtApiClient", () => {
  it("uses same-origin api base when VITE_AT_API_BASE_URL is configured", async () => {
    vi.resetModules();
    vi.stubEnv("VITE_AT_API_BASE_URL", "/api");
    const { getDefaultApiBaseUrl } = await import("./client");

    expect(getDefaultApiBaseUrl()).toBe("/api");
  });

  it("getHealth calls /api/health and returns parsed JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok", workspace: "demo" })
    });
    const client = new AtApiClient("http://localhost:8000", fetchMock);

    const result = await client.getHealth();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/health", {
      method: "GET",
      headers: { Accept: "application/json" }
    });
    expect(result).toEqual({ status: "ok", workspace: "demo" });
  });

  it("getProviders calls /api/providers", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ providers: [{ name: "mock", available: true, provider_type: "mock", detail: "ok" }] })
    });
    const client = new AtApiClient("http://localhost:8000", fetchMock);

    const result = await client.getProviders();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/providers", {
      method: "GET",
      headers: { Accept: "application/json" }
    });
    expect(result.providers[0].name).toBe("mock");
  });

  it("getProviderStatus calls the session provider-status endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        selected_provider: "auto",
        next_agent: "code",
        resolved_provider: "codex",
        available: false,
        detail: "command not found: codex"
      })
    });
    const client = new AtApiClient("http://localhost:8000", fetchMock);

    const result = await client.getProviderStatus("s 1");

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/sessions/s%201/provider-status", {
      method: "GET",
      headers: { Accept: "application/json" }
    });
    expect(result.resolved_provider).toBe("codex");
  });

  it("getFile requests the Chinese display copy by default", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ path: "agents/main/agent.md", content: "中文契约内容" })
    });
    const client = new AtApiClient("http://localhost:8000", fetchMock);

    const result = await client.getFile("agents/main/agent.md");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/file?path=agents%2Fmain%2Fagent.md&language=zh",
      { method: "GET", headers: { Accept: "application/json" } }
    );
    expect(result.content).toBe("中文契约内容");
  });

  it("getLanguage calls the session language endpoint", async () => {
    const body = {
      schema_version: 2,
      source_language: "zh",
      runtime_language: "en",
      display_language: "zh",
      artifact_mode: "bilingual",
      task_original: "任务",
      task_runtime: "Task",
      input_translation: { status: "completed", provider: "codex", error: null, updated_at: "now" },
      display_translation: { status: "pending", provider: "codex", error: null, updated_at: "now" }
    };
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
    const client = new AtApiClient("http://localhost:8000", fetchMock);

    const result = await client.getLanguage("s 1");

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/sessions/s%201/language", {
      method: "GET",
      headers: { Accept: "application/json" }
    });
    expect(result.runtime_language).toBe("en");
  });

  it("updateProvider sends a PATCH request", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, session: { id: "s1", provider: "opencode" } })
    });
    const client = new AtApiClient("http://localhost:8000", fetchMock);

    await client.updateProvider("s1", "opencode");

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/sessions/s1/provider", {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ provider: "opencode" })
    });
  });

  it("throws typed API error responses", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({
        error: {
          code: "file_not_allowed",
          message: "File is not allowed",
          retryable: false
        }
      })
    });
    const client = new AtApiClient("http://localhost:8000", fetchMock);

    await expect(client.getFile("../at.config.json")).rejects.toMatchObject({
      code: "file_not_allowed",
      message: "File is not allowed",
      retryable: false,
      status: 403
    });
  });

  it("binds the default fetcher to globalThis", async () => {
    const originalFetch = globalThis.fetch;
    const fetchMock = vi.fn(function (this: typeof globalThis) {
      expect(this).toBe(globalThis);
      return Promise.resolve({
        ok: true,
        json: async () => ({ status: "ok", workspace: "demo" })
      } as Response);
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    try {
      const client = new AtApiClient("http://localhost:8000");

      await expect(client.getHealth()).resolves.toEqual({ status: "ok", workspace: "demo" });
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

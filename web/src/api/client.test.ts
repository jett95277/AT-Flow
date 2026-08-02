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

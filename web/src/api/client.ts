import type {
  ApiErrorBody,
  ArtifactView,
  DoctorCheck,
  FileContentResponse,
  FileNode,
  HealthResponse,
  LanguageProfile,
  SessionState,
  AuditReport,
  CommandResult,
  ProviderCapability,
  ProviderStatus,
  TraceEvent
} from "./types";

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export class AtApiError extends Error {
  code: string;
  retryable: boolean;
  status: number;
  details?: Record<string, unknown>;

  constructor(status: number, body?: ApiErrorBody["error"]) {
    super(body?.message ?? `Request failed with status ${status}`);
    this.name = "AtApiError";
    this.code = body?.code ?? "api_error";
    this.retryable = body?.retryable ?? false;
    this.status = status;
    this.details = body?.details;
  }
}

export class AtApiClient {
  private readonly baseUrl: string;
  private readonly fetcher: FetchLike;

  constructor(baseUrl = getDefaultApiBaseUrl(), fetcher: FetchLike = defaultFetcher()) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.fetcher = fetcher;
  }

  getHealth(): Promise<HealthResponse> {
    return this.get("/api/health");
  }

  getDoctor(): Promise<{ checks: DoctorCheck[] }> {
    return this.get("/api/doctor");
  }

  getProviders(): Promise<{ providers: ProviderCapability[] }> {
    return this.get("/api/providers");
  }

  getSessions(): Promise<{ sessions: SessionState[] }> {
    return this.get("/api/sessions");
  }

  createSession(payload: { task: string; provider?: string }): Promise<CommandResult> {
    return this.post("/api/sessions", payload);
  }

  getState(sessionId: string): Promise<SessionState> {
    return this.get(`/api/sessions/${encodeURIComponent(sessionId)}/state`);
  }

  getProviderStatus(sessionId: string): Promise<ProviderStatus> {
    return this.get(`/api/sessions/${encodeURIComponent(sessionId)}/provider-status`);
  }

  getLanguage(sessionId: string): Promise<LanguageProfile> {
    return this.get(`/api/sessions/${encodeURIComponent(sessionId)}/language`);
  }

  updateProvider(sessionId: string, provider: string): Promise<CommandResult> {
    return this.patch(`/api/sessions/${encodeURIComponent(sessionId)}/provider`, { provider });
  }

  runOneStep(sessionId: string): Promise<CommandResult> {
    return this.post(`/api/sessions/${encodeURIComponent(sessionId)}/run-one-step`, {});
  }

  continueSession(sessionId: string): Promise<CommandResult> {
    return this.post(`/api/sessions/${encodeURIComponent(sessionId)}/continue`, {});
  }

  retrySession(sessionId: string): Promise<CommandResult> {
    return this.post(`/api/sessions/${encodeURIComponent(sessionId)}/retry`, {});
  }

  getTrace(sessionId: string): Promise<{ trace: TraceEvent[] }> {
    return this.get(`/api/sessions/${encodeURIComponent(sessionId)}/trace`);
  }

  getAudit(sessionId: string): Promise<{ audit: AuditReport[] }> {
    return this.get(`/api/sessions/${encodeURIComponent(sessionId)}/audit`);
  }

  getArtifact(sessionId: string, agent: string): Promise<ArtifactView> {
    return this.get(`/api/sessions/${encodeURIComponent(sessionId)}/artifact/${encodeURIComponent(agent)}`);
  }

  getWorkspaceTree(): Promise<{ tree: FileNode[] }> {
    return this.get("/api/workspace/tree");
  }

  getFile(path: string): Promise<FileContentResponse> {
    return this.get(`/api/file?path=${encodeURIComponent(path)}&language=zh`);
  }

  private async get<T>(path: string): Promise<T> {
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      method: "GET",
      headers: { Accept: "application/json" }
    });
    return parseResponse<T>(response);
  }

  private async post<T>(path: string, payload: unknown): Promise<T> {
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    return parseResponse<T>(response);
  }

  private async patch<T>(path: string, payload: unknown): Promise<T> {
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    return parseResponse<T>(response);
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON body (e.g. nginx error page or gateway timeout).
  }
  if (!response.ok) {
    const errorBody = (body ?? {}) as ApiErrorBody;
    throw new AtApiError(response.status, errorBody.error);
  }
  return body as T;
}

export function getDefaultApiBaseUrl(): string {
  return import.meta.env.VITE_AT_API_BASE_URL || "http://localhost:8000";
}

function defaultFetcher(): FetchLike {
  return globalThis.fetch.bind(globalThis);
}

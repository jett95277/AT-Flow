import type {
  ApiErrorBody,
  DoctorCheck,
  FileContentResponse,
  FileNode,
  HealthResponse,
  SessionState,
  AuditReport,
  CommandResult,
  TraceEvent
} from "./types";

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export class AtApiError extends Error {
  code: string;
  retryable: boolean;
  status: number;
  details?: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody["error"]) {
    super(body.message);
    this.name = "AtApiError";
    this.code = body.code;
    this.retryable = body.retryable;
    this.status = status;
    this.details = body.details;
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

  getSessions(): Promise<{ sessions: SessionState[] }> {
    return this.get("/api/sessions");
  }

  createSession(payload: { task: string; provider?: string }): Promise<CommandResult> {
    return this.post("/api/sessions", payload);
  }

  getState(sessionId: string): Promise<SessionState> {
    return this.get(`/api/sessions/${encodeURIComponent(sessionId)}/state`);
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

  getArtifact(sessionId: string, agent: string): Promise<{ artifact: string }> {
    return this.get(`/api/sessions/${encodeURIComponent(sessionId)}/artifact/${encodeURIComponent(agent)}`);
  }

  getWorkspaceTree(): Promise<{ tree: FileNode[] }> {
    return this.get("/api/workspace/tree");
  }

  getFile(path: string): Promise<FileContentResponse> {
    return this.get(`/api/file?path=${encodeURIComponent(path)}`);
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
}

async function parseResponse<T>(response: Response): Promise<T> {
  const body = await response.json();
  if (!response.ok) {
    const errorBody = body as ApiErrorBody;
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

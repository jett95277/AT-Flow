export type HealthResponse = {
  status: "ok";
  workspace: string;
};

export type DoctorCheck = {
  name: string;
  ok: boolean;
  detail: string;
};

export type FileNode = {
  name: string;
  path: string;
  kind: "directory" | "file";
  children: FileNode[];
};

export type SessionStep = {
  agent: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  artifact_path: string | null;
  error: string | null;
  failure_reason: string | null;
  retry_count: number;
  max_retries: number;
  retryable: boolean;
  input_paths: string[];
};

export type SessionState = {
  schema_version: number;
  id: string;
  task: string;
  project_path: string;
  provider: string;
  created_at: string;
  updated_at: string;
  status: string;
  current_stage: string | null;
  failure_reason: string | null;
  steps: SessionStep[];
};

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    retryable: boolean;
    details?: Record<string, unknown>;
  };
};

export type ApiErrorInfo = ApiErrorBody["error"];

export type CommandResult = {
  ok: boolean;
  session?: SessionState;
};

export type TraceEvent = Record<string, unknown> & {
  event?: string;
  agent?: string | null;
  status?: string | null;
};

export type AuditReport = Record<string, unknown> & {
  file?: string;
  agent?: string;
  violations?: unknown[];
};

export type FileContentResponse = {
  path: string;
  content: string;
};

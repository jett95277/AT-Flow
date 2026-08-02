export type HealthResponse = {
  status: "ok";
  workspace: string;
};

export type DoctorCheck = {
  name: string;
  ok: boolean;
  detail: string;
};

export type ProviderCapability = {
  name: string;
  available: boolean;
  provider_type: string;
  detail: string;
};

export type ProviderStatus = {
  selected_provider: string;
  next_agent: string | null;
  resolved_provider: string;
  available: boolean;
  detail: string;
};

export type TranslationState = {
  status: "disabled" | "not_required" | "pending" | "running" | "completed" | "failed";
  provider: string;
  error: string | null;
  updated_at: string;
};

export type LanguageProfile = {
  schema_version: 2;
  source_language: string;
  runtime_language: string;
  display_language: string;
  artifact_mode: string;
  task_original: string;
  task_runtime: string;
  input_translation: TranslationState;
  display_translation: TranslationState;
};

export type ArtifactView = {
  source: string;
  display: string | null;
  source_language: string;
  display_language: string;
  display_status: TranslationState["status"];
  display_provider: string;
  display_error: string | null;
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

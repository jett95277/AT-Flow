import type { SessionState } from "../api/types";

type RunControlsProps = {
  activeSession: SessionState | null;
  busy: boolean;
  task: string;
  initialProvider: string;
  providerOptions: string[];
  onTaskChange: (task: string) => void;
  onInitialProviderChange: (provider: string) => void;
  onCreateSession: () => void;
  onRunOneStep: (sessionId: string) => void;
  onContinue: (sessionId: string) => void;
  onRetry: (sessionId: string) => void;
  onRefreshDoctor: () => void;
};

export function RunControls({
  activeSession,
  busy,
  task,
  initialProvider,
  providerOptions,
  onTaskChange,
  onInitialProviderChange,
  onCreateSession,
  onRunOneStep,
  onContinue,
  onRetry,
  onRefreshDoctor
}: RunControlsProps) {
  const sessionId = activeSession?.id ?? null;
  const hasRunningStep = activeSession?.steps.some((step) => step.status === "running" || step.status === "retrying") ?? false;
  const hasQueuedStep = activeSession?.steps.some((step) => step.status === "queued") ?? false;
  const failedStep = activeSession?.steps.find((step) => step.status === "failed");
  const canRun =
    activeSession?.status === "queued" && sessionId !== null && hasQueuedStep && !hasRunningStep && !busy;
  const canRetry =
    sessionId !== null &&
    !hasRunningStep &&
    !busy &&
    failedStep !== undefined &&
    failedStep.retryable &&
    failedStep.retry_count < failedStep.max_retries;
  const createDisabled = task.trim().length === 0 || busy;

  return (
    <section className="runtime-block" aria-label="运行控制">
      <h3>运行控制</h3>
      <label className="provider-select">
        <span>任务</span>
        <textarea disabled={busy} value={task} rows={3} onChange={(event) => onTaskChange(event.target.value)} />
      </label>
      <label className="provider-select">
        <span>初始 CodeAgent</span>
        <select disabled={busy} value={initialProvider} onChange={(event) => onInitialProviderChange(event.target.value)}>
          {providerOptions.map((provider) => (
            <option key={provider} value={provider}>
              {provider}
            </option>
          ))}
        </select>
      </label>
      <div className="control-grid">
        <button type="button" disabled={createDisabled} onClick={onCreateSession}>
          创建会话
        </button>
        <button type="button" disabled={!canRun} onClick={() => sessionId && onRunOneStep(sessionId)}>
          执行一步
        </button>
        <button type="button" disabled={!canRun} onClick={() => sessionId && onContinue(sessionId)}>
          继续运行
        </button>
        <button type="button" disabled={!canRetry} onClick={() => sessionId && onRetry(sessionId)}>
          重试
        </button>
        <button type="button" onClick={onRefreshDoctor}>
          刷新诊断
        </button>
      </div>
    </section>
  );
}

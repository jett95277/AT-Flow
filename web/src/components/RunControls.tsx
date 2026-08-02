type RunControlsProps = {
  activeSessionId: string | null;
  selectedProvider: string;
  onProviderChange: (provider: string) => void;
  onCreateSession: () => void;
  onRunOneStep: (sessionId: string) => void;
  onContinue: (sessionId: string) => void;
  onRetry: (sessionId: string) => void;
  onRefreshDoctor: () => void;
};

const PROVIDERS = [
  { value: "mock", label: "mock" },
  { value: "auto", label: "auto" },
  { value: "codex", label: "codex" },
  { value: "opencode", label: "opencode" }
];

export function RunControls({
  activeSessionId,
  selectedProvider,
  onProviderChange,
  onCreateSession,
  onRunOneStep,
  onContinue,
  onRetry,
  onRefreshDoctor
}: RunControlsProps) {
  const disabled = activeSessionId === null;

  return (
    <section className="runtime-block" aria-label="运行控制">
      <h3>运行控制</h3>
      <label className="provider-select">
        <span>Provider</span>
        <select value={selectedProvider} onChange={(event) => onProviderChange(event.target.value)}>
          {PROVIDERS.map((provider) => (
            <option key={provider.value} value={provider.value}>
              {provider.label}
            </option>
          ))}
        </select>
      </label>
      <div className="control-grid">
        <button type="button" onClick={onCreateSession}>
          创建会话
        </button>
        <button type="button" disabled={disabled} onClick={() => activeSessionId && onRunOneStep(activeSessionId)}>
          执行一步
        </button>
        <button type="button" disabled={disabled} onClick={() => activeSessionId && onContinue(activeSessionId)}>
          继续运行
        </button>
        <button type="button" disabled={disabled} onClick={() => activeSessionId && onRetry(activeSessionId)}>
          重试
        </button>
        <button type="button" onClick={onRefreshDoctor}>
          刷新诊断
        </button>
      </div>
    </section>
  );
}

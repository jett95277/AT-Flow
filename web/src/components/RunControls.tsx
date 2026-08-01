type RunControlsProps = {
  activeSessionId: string | null;
  onCreateSession: () => void;
  onRunOneStep: (sessionId: string) => void;
  onContinue: (sessionId: string) => void;
  onRetry: (sessionId: string) => void;
  onRefreshDoctor: () => void;
};

export function RunControls({
  activeSessionId,
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

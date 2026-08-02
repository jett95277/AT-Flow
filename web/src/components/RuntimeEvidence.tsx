import type { ApiErrorInfo, ArtifactView, AuditReport, DoctorCheck, TraceEvent } from "../api/types";

type RuntimeEvidenceProps = {
  trace: TraceEvent[];
  audit: AuditReport[];
  doctor: DoctorCheck[];
  artifact: ArtifactView | null;
  error: ApiErrorInfo | null;
};

export function RuntimeEvidence({ trace, audit, doctor, artifact, error }: RuntimeEvidenceProps) {
  return (
    <section className="runtime-block" aria-label="运行证据">
      <h3>运行证据</h3>
      {error ? (
        <div className="evidence-error">
          <strong>{error.code}</strong>
          <span>{error.message}</span>
          <span>{error.retryable ? "可重试" : "不可重试"}</span>
        </div>
      ) : null}
      <EvidenceList title="追踪记录" emptyText="暂无追踪记录" rows={trace.map((event) => String(event.event ?? "event"))} />
      <EvidenceList title="审计报告" emptyText="暂无审计报告" rows={audit.map((report) => String(report.file ?? report.agent ?? "audit"))} />
      <DoctorList checks={doctor} />
      <div className="evidence-group">
        <h4>产物</h4>
        <ArtifactEvidence artifact={artifact} />
      </div>
    </section>
  );
}

function ArtifactEvidence({ artifact }: { artifact: ArtifactView | null }) {
  if (!artifact || !artifact.source) {
    return <pre>暂无产物</pre>;
  }
  const displayReady = artifact.display_status === "completed" && artifact.display;
  return (
    <div className="artifact-evidence">
      {displayReady ? <pre>{artifact.display}</pre> : null}
      {artifact.display_status === "failed" ? (
        <div className="artifact-translation-error">
          <strong>中文展示生成失败</strong>
          <span>{artifact.display_error || "翻译 Provider 未返回可用结果"}</span>
        </div>
      ) : null}
      {!displayReady && artifact.display_status !== "failed" ? (
        <p className="empty-text">中文展示状态：{artifact.display_status}</p>
      ) : null}
      <details>
        <summary>英文源产物</summary>
        <pre>{artifact.source}</pre>
      </details>
    </div>
  );
}

function DoctorList({ checks }: { checks: DoctorCheck[] }) {
  return (
    <div className="evidence-group">
      <h4>诊断检查</h4>
      {checks.length === 0 ? (
        <p className="empty-text">暂无诊断检查</p>
      ) : (
        <ul>
          {checks.map((check) => (
            <li key={check.name}>
              <strong>{check.name}</strong>
              <span>{check.ok ? "OK" : "FAIL"}</span>
              <span>{check.detail}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EvidenceList({ title, emptyText, rows }: { title: string; emptyText: string; rows: string[] }) {
  return (
    <div className="evidence-group">
      <h4>{title}</h4>
      {rows.length === 0 ? (
        <p className="empty-text">{emptyText}</p>
      ) : (
        <ul>
          {rows.map((row, index) => (
            <li key={`${row}-${index}`}>{row}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

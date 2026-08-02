import type { ApiErrorInfo, AuditReport, DoctorCheck, TraceEvent } from "../api/types";

type RuntimeEvidenceProps = {
  trace: TraceEvent[];
  audit: AuditReport[];
  doctor: DoctorCheck[];
  artifact: string | null;
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
        </div>
      ) : null}
      <EvidenceList title="追踪记录" emptyText="暂无追踪记录" rows={trace.map((event) => String(event.event ?? "event"))} />
      <EvidenceList title="审计报告" emptyText="暂无审计报告" rows={audit.map((report) => String(report.file ?? report.agent ?? "audit"))} />
      <DoctorList checks={doctor} />
      <div className="evidence-group">
        <h4>产物</h4>
        <pre>{artifact || "暂无产物"}</pre>
      </div>
    </section>
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

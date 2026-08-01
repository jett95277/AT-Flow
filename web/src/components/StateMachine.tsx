import type { SessionState } from "../api/types";
import { statusLabel } from "./labels";

type StateMachineProps = {
  session: SessionState | null;
};

export function StateMachine({ session }: StateMachineProps) {
  if (!session) {
    return (
      <section className="runtime-block" aria-label="状态机">
        <h3>状态机</h3>
        <p className="empty-text">暂无活动会话</p>
      </section>
    );
  }

  return (
    <section className="runtime-block" aria-label="状态机">
      <h3>状态机</h3>
      <p className="session-state">会话状态：{statusLabel(session.status)}</p>
      <div className="state-grid">
        {session.steps.map((step) => (
          <div className={`state-node state-${step.status}`} key={step.agent}>
            <strong>{step.agent}</strong>
            <span>{statusLabel(step.status)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

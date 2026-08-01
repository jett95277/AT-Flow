import type { SessionState } from "../api/types";
import { statusLabel } from "./labels";

type SessionListProps = {
  sessions: SessionState[];
};

export function SessionList({ sessions }: SessionListProps) {
  return (
    <section className="panel-section" aria-label="会话列表">
      <h2>会话</h2>
      {sessions.length === 0 ? (
        <p className="empty-text">暂无会话</p>
      ) : (
        <ul className="session-list">
          {sessions.map((session) => (
            <li key={session.id}>
              <strong>{session.id}</strong>
              <span>{statusLabel(session.status)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

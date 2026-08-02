import type { SessionState } from "../api/types";
import { statusLabel } from "./labels";

type SessionListProps = {
  sessions: SessionState[];
  activeSessionId: string | null;
  onSelect: (session: SessionState) => void;
};

export function SessionList({ sessions, activeSessionId, onSelect }: SessionListProps) {
  return (
    <section className="panel-section" aria-label="会话列表">
      <h2>会话</h2>
      {sessions.length === 0 ? (
        <p className="empty-text">暂无会话</p>
      ) : (
        <ul className="session-list">
          {sessions.map((session) => (
            <li key={session.id}>
              <button
                type="button"
                className={activeSessionId === session.id ? "session-item active" : "session-item"}
                aria-current={activeSessionId === session.id ? "true" : undefined}
                onClick={() => onSelect(session)}
              >
                <strong>{session.id}</strong>
                <span>
                  {statusLabel(session.status)} · {session.current_stage}
                </span>
                <time dateTime={session.updated_at}>{session.updated_at}</time>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

import type { HealthResponse } from "../api/types";

type TopBarProps = {
  health: HealthResponse | null;
  error: string | null;
};

export function TopBar({ health, error }: TopBarProps) {
  return (
    <header className="top-bar" role="banner">
      <div>
        <strong>AT Flow 控制台</strong>
        <span className="workspace-label">{health?.workspace ?? "工作区连接中"}</span>
      </div>
      <div className="top-bar-status">
        <span className={health ? "status-ok" : "status-muted"}>{health ? "后端正常" : "检查中"}</span>
        {error ? <span className="status-error">{error}</span> : null}
      </div>
    </header>
  );
}

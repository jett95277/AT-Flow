import { useEffect, useState } from "react";

import type { AtApiClient } from "../api/client";
import type { ApiErrorInfo, AuditReport, FileNode, HealthResponse, SessionState, TraceEvent } from "../api/types";
import { DocumentViewer } from "./DocumentViewer";
import { RunControls } from "./RunControls";
import { RuntimeEvidence } from "./RuntimeEvidence";
import { SessionList } from "./SessionList";
import { StateMachine } from "./StateMachine";
import { TopBar } from "./TopBar";
import { WorkspaceTree } from "./WorkspaceTree";

type AppShellProps = {
  client: AtApiClient;
};

export function AppShell({ client }: AppShellProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [sessions, setSessions] = useState<SessionState[]>([]);
  const [activeSession, setActiveSession] = useState<SessionState | null>(null);
  const [tree, setTree] = useState<FileNode[]>([]);
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [audit, setAudit] = useState<AuditReport[]>([]);
  const [artifact, setArtifact] = useState<string | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [documentContent, setDocumentContent] = useState<string | null>(null);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([client.getHealth(), client.getSessions(), client.getWorkspaceTree()])
      .then(([healthResponse, sessionsResponse, treeResponse]) => {
        setHealth(healthResponse);
        setSessions(sessionsResponse.sessions);
        setActiveSession(sessionsResponse.sessions[0] ?? null);
        setTree(treeResponse.tree);
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "后端不可用");
      });
  }, [client]);

  useEffect(() => {
    if (!activeSession) {
      return;
    }
    const sessionId = activeSession.id;
    const stateTimer = window.setInterval(() => {
      client.getState(sessionId).then(setActiveSession).catch(captureError);
    }, 1000);
    const traceTimer = window.setInterval(() => {
      client.getTrace(sessionId).then((response) => setTrace(response.trace)).catch(captureError);
    }, 2000);
    const auditTimer = window.setInterval(() => {
      client.getAudit(sessionId).then((response) => setAudit(response.audit)).catch(captureError);
    }, 3000);

    client.getTrace(sessionId).then((response) => setTrace(response.trace)).catch(captureError);
    client.getAudit(sessionId).then((response) => setAudit(response.audit)).catch(captureError);
    refreshArtifact(activeSession);

    return () => {
      window.clearInterval(stateTimer);
      window.clearInterval(traceTimer);
      window.clearInterval(auditTimer);
    };
  }, [activeSession?.id, client]);

  function selectFile(path: string) {
    setSelectedPath(path);
    setDocumentLoading(true);
    client
      .getFile(path)
      .then((response) => {
        setDocumentContent(response.content);
      })
      .catch((caught: unknown) => {
        setDocumentContent(caught instanceof Error ? caught.message : "无法加载文件");
      })
      .finally(() => setDocumentLoading(false));
  }

  function captureError(caught: unknown) {
    setError(caught instanceof Error ? caught.message : "运行时请求失败");
  }

  function refreshArtifact(session: SessionState) {
    const doneStep = session.steps.find((step) => step.status === "done");
    if (!doneStep) {
      setArtifact(null);
      return;
    }
    client
      .getArtifact(session.id, doneStep.agent)
      .then((response) => setArtifact(response.artifact))
      .catch(captureError);
  }

  function createSession() {
    client
      .createSession({ task: "Web 控制台演示任务", provider: "mock" })
      .then((response) => {
        if (response.session) {
          setActiveSession(response.session);
          setSessions((current) => [response.session as SessionState, ...current]);
        }
      })
      .catch(captureError);
  }

  function runCommand(command: (sessionId: string) => Promise<{ session?: SessionState }>, sessionId: string) {
    command(sessionId)
      .then((response) => {
        if (response.session) {
          setActiveSession(response.session);
          setSessions((current) =>
            current.map((session) => (session.id === response.session?.id ? response.session : session))
          );
          refreshArtifact(response.session);
        }
      })
      .catch(captureError);
  }

  return (
    <div className="app-shell">
      <TopBar health={health} error={error} />
      <div className="console-grid">
        <aside className="left-panel">
          <SessionList sessions={sessions} />
          <WorkspaceTree tree={tree} selectedPath={selectedPath} onSelect={selectFile} />
        </aside>
        <DocumentViewer path={selectedPath} content={documentContent} loading={documentLoading} />
        <section className="runtime-panel" aria-label="运行时检查器">
          <h2>运行时检查器</h2>
          <RunControls
            activeSessionId={activeSession?.id ?? null}
            onCreateSession={createSession}
            onRunOneStep={(sessionId) => runCommand(client.runOneStep.bind(client), sessionId)}
            onContinue={(sessionId) => runCommand(client.continueSession.bind(client), sessionId)}
            onRetry={(sessionId) => runCommand(client.retrySession.bind(client), sessionId)}
            onRefreshDoctor={() => client.getDoctor().catch(captureError)}
          />
          <StateMachine session={activeSession} />
          <RuntimeEvidence
            trace={trace}
            audit={audit}
            artifact={artifact}
            error={error ? ({ code: "客户端错误", message: error, retryable: false } satisfies ApiErrorInfo) : null}
          />
        </section>
      </div>
    </div>
  );
}

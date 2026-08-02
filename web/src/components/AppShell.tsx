import { useEffect, useState } from "react";

import { AtApiError, type AtApiClient } from "../api/client";
import type {
  ApiErrorInfo,
  ArtifactView,
  AuditReport,
  DoctorCheck,
  FileNode,
  HealthResponse,
  ProviderCapability,
  ProviderStatus,
  SessionState,
  TraceEvent
} from "../api/types";
import { CodeAgentPanel } from "./CodeAgentPanel";
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
  const [doctor, setDoctor] = useState<DoctorCheck[]>([]);
  const [providers, setProviders] = useState<ProviderCapability[]>([]);
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null);
  const [artifact, setArtifact] = useState<ArtifactView | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [documentContent, setDocumentContent] = useState<string | null>(null);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [error, setError] = useState<ApiErrorInfo | null>(null);
  const [taskDraft, setTaskDraft] = useState("");
  const [initialProvider, setInitialProvider] = useState("mock");
  const [mutationPending, setMutationPending] = useState(false);

  useEffect(() => {
    Promise.all([client.getHealth(), client.getSessions(), client.getWorkspaceTree(), client.getProviders()])
      .then(([healthResponse, sessionsResponse, treeResponse, providersResponse]) => {
        setHealth(healthResponse);
        setSessions(sessionsResponse.sessions);
        setActiveSession(sessionsResponse.sessions[0] ?? null);
        setTree(treeResponse.tree);
        setProviders(providersResponse.providers);
      })
      .catch((caught: unknown) => {
        setError(toApiError(caught, "后端不可用"));
      });
  }, [client]);

  useEffect(() => {
    if (!activeSession) {
      return;
    }
    let current = true;
    const isCurrent = () => current;
    const captureCurrentError = (caught: unknown) => {
      if (isCurrent()) {
        captureError(caught);
      }
    };
    const sessionId = activeSession.id;
    const stateTimer = window.setInterval(() => {
      client
        .getState(sessionId)
        .then((session) => {
          if (!isCurrent()) {
            return;
          }
          setActiveSession(session);
          refreshProviderStatus(session.id, isCurrent);
        })
        .catch(captureCurrentError);
    }, 1000);
    const traceTimer = window.setInterval(() => {
      client
        .getTrace(sessionId)
        .then((response) => {
          if (isCurrent()) {
            setTrace(response.trace);
          }
        })
        .catch(captureCurrentError);
    }, 2000);
    const auditTimer = window.setInterval(() => {
      client
        .getAudit(sessionId)
        .then((response) => {
          if (isCurrent()) {
            setAudit(response.audit);
          }
        })
        .catch(captureCurrentError);
    }, 3000);

    client
      .getTrace(sessionId)
      .then((response) => {
        if (isCurrent()) {
          setTrace(response.trace);
        }
      })
      .catch(captureCurrentError);
    client
      .getAudit(sessionId)
      .then((response) => {
        if (isCurrent()) {
          setAudit(response.audit);
        }
      })
      .catch(captureCurrentError);
    refreshProviderStatus(sessionId, isCurrent);
    refreshArtifact(activeSession, isCurrent);

    return () => {
      current = false;
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

  function selectSession(session: SessionState) {
    setTrace([]);
    setAudit([]);
    setArtifact(null);
    setProviderStatus(null);
    setError(null);
    setActiveSession(session);
  }

  function captureError(caught: unknown) {
    setError(toApiError(caught, "运行时请求失败"));
  }

  function refreshArtifact(session: SessionState, isCurrent: () => boolean = () => true) {
    const doneStep = session.steps.find((step) => step.status === "done");
    if (!doneStep) {
      if (isCurrent()) {
        setArtifact(null);
      }
      return;
    }
    client
      .getArtifact(session.id, doneStep.agent)
      .then((response) => {
        if (isCurrent()) {
          setArtifact(response);
        }
      })
      .catch((caught: unknown) => {
        if (isCurrent()) {
          captureError(caught);
        }
      });
  }

  function createSession() {
    const task = taskDraft.trim();
    if (!task) {
      return;
    }
    setError(null);
    setMutationPending(true);
    client
      .createSession({ task, provider: initialProvider })
      .then((response) => {
        setError(null);
        if (response.session) {
          setActiveSession(response.session);
          setSessions((current) => [response.session as SessionState, ...current]);
          refreshProviderStatus(response.session.id);
          setTaskDraft("");
        }
      })
      .catch(captureError)
      .finally(() => setMutationPending(false));
  }

  function replaceSession(session: SessionState) {
    setActiveSession(session);
    setSessions((current) => current.map((item) => (item.id === session.id ? session : item)));
    refreshProviderStatus(session.id);
  }

  function runCommand(command: (sessionId: string) => Promise<{ session?: SessionState }>, sessionId: string) {
    setError(null);
    setMutationPending(true);
    command(sessionId)
      .then((response) => {
        setError(null);
        if (response.session) {
          replaceSession(response.session);
          refreshArtifact(response.session);
        }
      })
      .catch(captureError)
      .finally(() => setMutationPending(false));
  }

  function refreshDoctor() {
    setError(null);
    client
      .getDoctor()
      .then((response) => {
        setDoctor(response.checks);
        setError(null);
      })
      .catch(captureError);
  }

  function refreshProviderStatus(sessionId: string, isCurrent: () => boolean = () => true) {
    client
      .getProviderStatus(sessionId)
      .then((status) => {
        if (isCurrent()) {
          setProviderStatus(status);
        }
      })
      .catch((caught: unknown) => {
        if (isCurrent()) {
          captureError(caught);
        }
      });
  }

  function switchProvider(provider: string) {
    if (!activeSession) {
      return;
    }
    setError(null);
    setMutationPending(true);
    client
      .updateProvider(activeSession.id, provider)
      .then((response) => {
        setError(null);
        if (response.session) {
          replaceSession(response.session);
        }
      })
      .catch(captureError)
      .finally(() => setMutationPending(false));
  }

  return (
    <div className="app-shell">
      <TopBar health={health} error={error} />
      <div className="console-grid">
        <aside className="left-panel" data-scroll-region="left">
          <SessionList
            sessions={sessions}
            activeSessionId={activeSession?.id ?? null}
            onSelect={selectSession}
          />
          <WorkspaceTree tree={tree} selectedPath={selectedPath} onSelect={selectFile} />
        </aside>
        <main className="middle-panel" data-scroll-region="middle">
          <CodeAgentPanel
            activeSession={activeSession}
            providers={providers}
            providerStatus={providerStatus}
            busy={mutationPending}
            onSwitchProvider={switchProvider}
          />
          <DocumentViewer path={selectedPath} content={documentContent} loading={documentLoading} />
        </main>
        <section className="runtime-panel" aria-label="运行时检查器" data-scroll-region="runtime">
          <h2>运行时检查器</h2>
          <RunControls
            activeSession={activeSession}
            busy={mutationPending}
            task={taskDraft}
            initialProvider={initialProvider}
            providerOptions={providers.length > 0 ? providers.map((provider) => provider.name) : ["mock", "auto", "codex", "opencode"]}
            onTaskChange={setTaskDraft}
            onInitialProviderChange={setInitialProvider}
            onCreateSession={createSession}
            onRunOneStep={(sessionId) => runCommand(client.runOneStep.bind(client), sessionId)}
            onContinue={(sessionId) => runCommand(client.continueSession.bind(client), sessionId)}
            onRetry={(sessionId) => runCommand(client.retrySession.bind(client), sessionId)}
            onRefreshDoctor={refreshDoctor}
          />
          <StateMachine session={activeSession} />
          <RuntimeEvidence
            trace={trace}
            audit={audit}
            doctor={doctor}
            artifact={artifact}
            error={error}
          />
        </section>
      </div>
    </div>
  );
}

function toApiError(caught: unknown, fallbackMessage: string): ApiErrorInfo {
  if (caught instanceof AtApiError) {
    return {
      code: caught.code,
      message: caught.message,
      retryable: caught.retryable,
      details: caught.details
    };
  }
  return {
    code: "client_error",
    message: caught instanceof Error ? caught.message : fallbackMessage,
    retryable: false
  };
}

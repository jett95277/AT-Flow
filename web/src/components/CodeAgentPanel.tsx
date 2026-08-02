import type { ProviderCapability, ProviderStatus, SessionState } from "../api/types";

type CodeAgentPanelProps = {
  activeSession: SessionState | null;
  providers: ProviderCapability[];
  providerStatus: ProviderStatus | null;
  busy: boolean;
  onSwitchProvider: (provider: string) => void;
};

const FALLBACK_PROVIDERS: ProviderCapability[] = [
  { name: "auto", available: true, provider_type: "routing", detail: "routes by agent" },
  { name: "mock", available: true, provider_type: "mock", detail: "mock provider is always available" },
  { name: "codex", available: false, provider_type: "process", detail: "provider status not loaded" },
  { name: "opencode", available: false, provider_type: "process", detail: "provider status not loaded" }
];

export function CodeAgentPanel({
  activeSession,
  providers,
  providerStatus,
  busy,
  onSwitchProvider
}: CodeAgentPanelProps) {
  const options = providers.length > 0 ? providers : FALLBACK_PROVIDERS;
  const selectedProvider = providerStatus?.selected_provider ?? activeSession?.provider ?? "mock";
  const resolvedProvider = providerStatus?.resolved_provider ?? selectedProvider;
  const nextAgent = providerStatus?.next_agent ?? activeSession?.current_stage ?? "无";
  const statusDetail = providerStatus?.detail ?? "等待后端状态";
  const available = providerStatus?.available ?? false;
  const switchLocked =
    busy ||
    !activeSession ||
    activeSession.steps.some((step) => step.status === "running" || step.status === "retrying");

  return (
    <section className="code-agent-panel panel-section" aria-label="CodeAgent 切换">
      <div className="panel-heading">
        <h2>CodeAgent 切换</h2>
        <span>{activeSession ? activeSession.id : "暂无会话"}</span>
      </div>
      <label className="code-agent-selector">
        <span>选择 CodeAgent</span>
        <select
          value={selectedProvider}
          disabled={switchLocked}
          onChange={(event) => onSwitchProvider(event.target.value)}
        >
          {options.map((provider) => (
            <option key={provider.name} value={provider.name}>
              {provider.name}
            </option>
          ))}
        </select>
      </label>
      <div className="code-agent-summary">
        <Metric label="当前 CodeAgent" value={selectedProvider} />
        <Metric label="解析 Provider" value={resolvedProvider} />
        <Metric label="下一 Agent" value={nextAgent} />
        <Metric label="可用状态" value={available ? "可用" : "不可用"} tone={available ? "ok" : "warn"} />
      </div>
      <p className="code-agent-detail">{statusDetail}</p>
      <ul className="provider-catalog">
        {options.map((provider) => (
          <li key={provider.name}>
            <span>{provider.name}</span>
            <strong className={provider.available ? "status-ok-text" : "status-warn-text"}>
              {provider.available ? "可用" : "不可用"}
            </strong>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "ok" | "warn" }) {
  return (
    <div className="code-agent-metric">
      <span>{label}</span>
      <strong className={tone === "ok" ? "status-ok-text" : tone === "warn" ? "status-warn-text" : undefined}>
        {value}
      </strong>
    </div>
  );
}

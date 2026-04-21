import {
  formatBooleanLabel,
  formatLabel,
  formatNumber,
  summarizeReanchor,
} from "@/features/autonomy/formatters";
import {
  ActionButton,
  PanelMessage,
  SectionHeader,
  StatusPill,
  TableCell,
  TableHeader,
} from "@/features/autonomy/components/ui";

export default function AgentsPanel({
  actionKey,
  activeRunCountByAgent,
  agentForm,
  agents,
  autonomyStatus,
  budgetByAgent,
  escalationCountByAgent,
  formError,
  latestCheckpointByAgent,
  onAgentFormChange,
  onCreateAgent,
  onPause,
  onResume,
  onStop,
  resourceError,
}) {
  return (
    <section className="autonomy-panel">
      <SectionHeader
        title="Agents"
        count={agents.length}
        description="Pause, resume, stop, and inspect bounded operator agents."
      />
      {resourceError ? <PanelMessage text={resourceError} tone="error" /> : null}
      <div className="autonomy-tableWrap">
        <table className="autonomy-table">
          <thead>
            <tr>
              <TableHeader>Agent</TableHeader>
              <TableHeader>Status</TableHeader>
              <TableHeader>Style profile</TableHeader>
              <TableHeader>Attention mode</TableHeader>
              <TableHeader>Novelty budget</TableHeader>
              <TableHeader>Re-anchor due</TableHeader>
              <TableHeader>Interrupt queue</TableHeader>
              <TableHeader>Active runs</TableHeader>
              <TableHeader>Escalations</TableHeader>
              <TableHeader>Last re-anchor</TableHeader>
              <TableHeader>Actions</TableHeader>
            </tr>
          </thead>
          <tbody>
            {agents.length === 0 ? (
              <tr>
                <TableCell colSpan={11}>No autonomy agents returned.</TableCell>
              </tr>
            ) : (
              agents.map((agent) => {
                const latestCheckpoint = latestCheckpointByAgent[agent.agent_id];
                const budgetLedger = budgetByAgent[agent.agent_id];
                const pendingEscalations = escalationCountByAgent[agent.agent_id] || 0;
                const activeRunCount = activeRunCountByAgent[agent.agent_id] || 0;
                return (
                  <tr key={agent.agent_id}>
                    <TableCell>
                      <div className="autonomy-strongCell">{agent.name}</div>
                      <div className="autonomy-subtleCell">{agent.agent_id}</div>
                    </TableCell>
                    <TableCell>
                      <StatusPill
                        tone={
                          agent.status === "active"
                            ? "success"
                            : agent.status === "paused"
                              ? "warning"
                              : "danger"
                        }
                        value={formatLabel(agent.status)}
                      />
                    </TableCell>
                    <TableCell>{agent.style_profile_id}</TableCell>
                    <TableCell>{formatLabel(latestCheckpoint?.current_attention_mode)}</TableCell>
                    <TableCell>
                      {formatNumber(
                        latestCheckpoint?.novelty_budget_remaining,
                        formatNumber(autonomyStatus?.novelty_budget_remaining)
                      )}
                    </TableCell>
                    <TableCell>{formatBooleanLabel(latestCheckpoint?.reanchor_due)}</TableCell>
                    <TableCell>{formatNumber(latestCheckpoint?.interrupt_queue_length, "0")}</TableCell>
                    <TableCell>{formatNumber(activeRunCount, "0")}</TableCell>
                    <TableCell>{formatNumber(pendingEscalations, "0")}</TableCell>
                    <TableCell>{summarizeReanchor(latestCheckpoint?.last_reanchor_summary)}</TableCell>
                    <TableCell>
                      <div className="autonomy-inlineActions autonomy-inlineActions--table">
                        <ActionButton
                          busy={actionKey === `pause:${agent.agent_id}`}
                          disabled={agent.status === "paused"}
                          onClick={() => onPause(agent)}
                        >
                          Pause
                        </ActionButton>
                        <ActionButton
                          busy={actionKey === `resume:${agent.agent_id}`}
                          disabled={agent.status === "active"}
                          onClick={() => onResume(agent)}
                          tone="success"
                        >
                          Resume
                        </ActionButton>
                        <ActionButton
                          busy={actionKey === `stop:${agent.agent_id}`}
                          disabled={agent.status === "stopped"}
                          onClick={() => onStop(agent)}
                          tone="danger"
                        >
                          Stop
                        </ActionButton>
                      </div>
                      {budgetLedger ? (
                        <div className="autonomy-subtleCell">
                          Steps {formatNumber(budgetLedger.total_steps_observed, "0")} • Retries {formatNumber(budgetLedger.total_retries_used, "0")}
                        </div>
                      ) : null}
                    </TableCell>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <form className="autonomy-form" onSubmit={onCreateAgent}>
        <div className="autonomy-formTitle">Create agent</div>
        <div className="autonomy-formGrid autonomy-formGrid--three">
          <label className="autonomy-field">
            <span className="autonomy-fieldLabel">Name</span>
            <input className="autonomy-input" onChange={(event) => onAgentFormChange("name", event.target.value)} value={agentForm.name} />
          </label>
          <label className="autonomy-field">
            <span className="autonomy-fieldLabel">Description</span>
            <input className="autonomy-input" onChange={(event) => onAgentFormChange("description", event.target.value)} value={agentForm.description} />
          </label>
          <label className="autonomy-field">
            <span className="autonomy-fieldLabel">Style profile id</span>
            <input className="autonomy-input" onChange={(event) => onAgentFormChange("styleProfileId", event.target.value)} value={agentForm.styleProfileId} />
          </label>
          <label className="autonomy-field">
            <span className="autonomy-fieldLabel">Max steps / run</span>
            <input className="autonomy-input" min="1" onChange={(event) => onAgentFormChange("maxStepsPerRun", event.target.value)} type="number" value={agentForm.maxStepsPerRun} />
          </label>
          <label className="autonomy-field">
            <span className="autonomy-fieldLabel">Max runs / agent</span>
            <input className="autonomy-input" min="1" onChange={(event) => onAgentFormChange("maxRunsPerAgent", event.target.value)} type="number" value={agentForm.maxRunsPerAgent} />
          </label>
          <label className="autonomy-field">
            <span className="autonomy-fieldLabel">Max parallel runs</span>
            <input className="autonomy-input" min="1" onChange={(event) => onAgentFormChange("maxParallelRuns", event.target.value)} type="number" value={agentForm.maxParallelRuns} />
          </label>
          <label className="autonomy-field">
            <span className="autonomy-fieldLabel">Max retries / step</span>
            <input className="autonomy-input" min="0" onChange={(event) => onAgentFormChange("maxRetriesPerStep", event.target.value)} type="number" value={agentForm.maxRetriesPerStep} />
          </label>
          <label className="autonomy-field">
            <span className="autonomy-fieldLabel">Max run duration (s)</span>
            <input className="autonomy-input" min="1" onChange={(event) => onAgentFormChange("maxRunDurationSeconds", event.target.value)} type="number" value={agentForm.maxRunDurationSeconds} />
          </label>
          <label className="autonomy-field">
            <span className="autonomy-fieldLabel">Deadman timeout (s)</span>
            <input className="autonomy-input" min="1" onChange={(event) => onAgentFormChange("deadmanTimeoutSeconds", event.target.value)} type="number" value={agentForm.deadmanTimeoutSeconds} />
          </label>
        </div>

        <div className="autonomy-toggleRow">
          <label className="autonomy-checkbox">
            <input checked={agentForm.enabled} onChange={(event) => onAgentFormChange("enabled", event.target.checked)} type="checkbox" />
            Policy enabled
          </label>
          <label className="autonomy-checkbox">
            <input checked={agentForm.allowMemoryWrites} onChange={(event) => onAgentFormChange("allowMemoryWrites", event.target.checked)} type="checkbox" />
            Allow memory writes
          </label>
          <label className="autonomy-checkbox">
            <input checked={agentForm.allowExternalWrites} onChange={(event) => onAgentFormChange("allowExternalWrites", event.target.checked)} type="checkbox" />
            Allow external writes
          </label>
          <label className="autonomy-checkbox">
            <input checked={agentForm.autoResumeAfterApproval} onChange={(event) => onAgentFormChange("autoResumeAfterApproval", event.target.checked)} type="checkbox" />
            Auto-resume after approval
          </label>
        </div>

        {formError ? <PanelMessage text={formError} tone="error" /> : null}
        <div className="autonomy-formActions">
          <ActionButton busy={actionKey === "create-agent"} type="submit" tone="success">
            Create agent
          </ActionButton>
        </div>
      </form>
    </section>
  );
}
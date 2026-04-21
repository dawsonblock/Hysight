import {
  formatBooleanLabel,
  formatLabel,
  formatNumber,
  formatTimestamp,
  summarizeReanchor,
} from "@/features/autonomy/formatters";
import { MetricCard, PanelMessage, SectionHeader } from "@/features/autonomy/components/ui";

export default function AutonomyStatusHeader({ autonomyStatus, budgets, loading, resourceError, supervisorTone }) {
  return (
    <section className="autonomy-panel">
      <SectionHeader
        title="Supervisor status"
        description="Compact operator summary of the backend autonomy supervisor."
      />
      {resourceError ? <PanelMessage text={resourceError} tone="error" /> : null}
      {loading && !autonomyStatus ? (
        <PanelMessage text="Loading autonomy supervisor state…" />
      ) : autonomyStatus ? (
        <div className="autonomy-metricGrid">
          <MetricCard
            label="Supervisor"
            value={autonomyStatus.running ? "Running" : "Stopped"}
            hint={`Enabled: ${formatBooleanLabel(autonomyStatus.enabled)} • Loop: ${formatBooleanLabel(autonomyStatus.loop_running)}`}
            tone={supervisorTone}
          />
          <MetricCard
            label="Kill switch"
            value={autonomyStatus.kill_switch_active ? "Active" : "Clear"}
            hint={autonomyStatus.kill_switch_reason || "No active kill-switch reason."}
            tone={autonomyStatus.kill_switch_active ? "danger" : "success"}
          />
          <MetricCard
            label="Active agents"
            value={formatNumber(autonomyStatus.active_agents, "0")}
            hint={`Pending triggers: ${formatNumber(autonomyStatus.pending_triggers, "0")}`}
            tone="neutral"
          />
          <MetricCard
            label="Active autonomous runs"
            value={formatNumber(autonomyStatus.active_runs, "0")}
            hint={`Pending escalations: ${formatNumber(autonomyStatus.pending_escalations, "0")}`}
            tone={(autonomyStatus.pending_escalations || 0) > 0 ? "warning" : "neutral"}
          />
          <MetricCard
            label="Last decision"
            value={formatLabel(autonomyStatus.last_evaluator_decision)}
            hint={`Checkpoint: ${formatLabel(autonomyStatus.last_checkpoint?.status)}`}
            tone="neutral"
          />
          <MetricCard
            label="Last tick"
            value={formatTimestamp(autonomyStatus.last_tick_at)}
            hint={`Dedupe keys: ${formatNumber(autonomyStatus.dedupe_keys_tracked, "0")}`}
            tone="neutral"
          />
          <MetricCard
            label="Attention mode"
            value={formatLabel(autonomyStatus.current_attention_mode)}
            hint={`Interrupt queue: ${formatNumber(autonomyStatus.interrupt_queue_length, "0")}`}
            tone={autonomyStatus.reanchor_due ? "warning" : "neutral"}
          />
          <MetricCard
            label="Novelty budget"
            value={formatNumber(autonomyStatus.novelty_budget_remaining)}
            hint={`Hyperfocus steps used: ${formatNumber(autonomyStatus.hyperfocus_steps_used, "0")}`}
            tone="neutral"
          />
          <MetricCard
            label="Latest re-anchor"
            value={summarizeReanchor(autonomyStatus.last_reanchor_summary)}
            hint={`Last checkpointed: ${formatTimestamp(autonomyStatus.last_checkpoint?.checkpointed_at)}`}
            tone={autonomyStatus.reanchor_due ? "warning" : "neutral"}
          />
          <MetricCard
            label="Budget ledgers"
            value={formatNumber(budgets.length, "0")}
            hint={
              budgets[0]
                ? `Observed steps: ${formatNumber(budgets[0].total_steps_observed, "0")} • Retries: ${formatNumber(budgets[0].total_retries_used, "0")}`
                : "No budget ledgers returned."
            }
            tone="neutral"
          />
        </div>
      ) : (
        <PanelMessage text="No autonomy status returned by the backend." tone="error" />
      )}
    </section>
  );
}
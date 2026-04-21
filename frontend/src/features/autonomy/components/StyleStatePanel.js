import { formatBooleanLabel, formatLabel, formatNumber, summarizeReanchor } from "@/features/autonomy/formatters";
import { SectionHeader, TableCell, TableHeader } from "@/features/autonomy/components/ui";

export default function StyleStatePanel({ agents, autonomyStatus, latestCheckpointByAgent }) {
  return (
    <section className="autonomy-panel">
      <SectionHeader
        title="Style and attention"
        description="Operational style-layer state only. No human-like thoughts or medical framing."
      />
      <div className="autonomy-stylePanel">
        <div className="autonomy-styleSummary">
          <div>
            <div className="autonomy-keyValueLabel">Current attention mode</div>
            <div className="autonomy-keyValueValue">{formatLabel(autonomyStatus?.current_attention_mode)}</div>
          </div>
          <div>
            <div className="autonomy-keyValueLabel">Hyperfocus active</div>
            <div className="autonomy-keyValueValue">
              {autonomyStatus?.hyperfocus_steps_used === null || autonomyStatus?.hyperfocus_steps_used === undefined
                ? "Unavailable"
                : autonomyStatus.hyperfocus_steps_used > 0
                  ? "Active"
                  : "Inactive"}
            </div>
          </div>
          <div>
            <div className="autonomy-keyValueLabel">Re-anchor due</div>
            <div className="autonomy-keyValueValue">{formatBooleanLabel(autonomyStatus?.reanchor_due)}</div>
          </div>
          <div>
            <div className="autonomy-keyValueLabel">Queued branches / interrupts</div>
            <div className="autonomy-keyValueValue">{formatNumber(autonomyStatus?.interrupt_queue_length, "0")}</div>
          </div>
          <div>
            <div className="autonomy-keyValueLabel">Latest re-anchor summary</div>
            <div className="autonomy-keyValueValue autonomy-keyValueValue--wrap">{summarizeReanchor(autonomyStatus?.last_reanchor_summary)}</div>
          </div>
        </div>

        <div className="autonomy-tableWrap">
          <table className="autonomy-table">
            <thead>
              <tr>
                <TableHeader>Agent</TableHeader>
                <TableHeader>Style profile</TableHeader>
                <TableHeader>Attention</TableHeader>
                <TableHeader>Hyperfocus steps</TableHeader>
                <TableHeader>Novelty remaining</TableHeader>
                <TableHeader>Re-anchor summary</TableHeader>
              </tr>
            </thead>
            <tbody>
              {agents.length === 0 ? (
                <tr><TableCell colSpan={6}>No agents available for style inspection.</TableCell></tr>
              ) : (
                agents.map((agent) => {
                  const latestCheckpoint = latestCheckpointByAgent[agent.agent_id];
                  return (
                    <tr key={`style:${agent.agent_id}`}>
                      <TableCell>{agent.name}</TableCell>
                      <TableCell>{latestCheckpoint?.style_profile_id || agent.style_profile_id}</TableCell>
                      <TableCell>{formatLabel(latestCheckpoint?.current_attention_mode)}</TableCell>
                      <TableCell>{formatNumber(latestCheckpoint?.hyperfocus_steps_used, "0")}</TableCell>
                      <TableCell>{formatNumber(latestCheckpoint?.novelty_budget_remaining)}</TableCell>
                      <TableCell>{summarizeReanchor(latestCheckpoint?.last_reanchor_summary)}</TableCell>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
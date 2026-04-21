import { formatLabel, formatNumber, summarizeReanchor } from "@/features/autonomy/formatters";
import { ActionButton, PanelMessage, SectionHeader, TableCell, TableHeader } from "@/features/autonomy/components/ui";

export default function CheckpointsPanel({ checkpoints, onOpenRun, resourceError }) {
  return (
    <section className="autonomy-panel">
      <SectionHeader
        title="Checkpoints"
        count={checkpoints.length}
        description="Inspection-only checkpoint history as exposed by the backend."
      />
      {resourceError ? <PanelMessage text={resourceError} tone="error" /> : null}
      <div className="autonomy-tableWrap autonomy-tableWrap--tall">
        <table className="autonomy-table">
          <thead>
            <tr>
              <TableHeader>Checkpoint</TableHeader>
              <TableHeader>Run</TableHeader>
              <TableHeader>Status</TableHeader>
              <TableHeader>Attempt</TableHeader>
              <TableHeader>Decision</TableHeader>
              <TableHeader>Attention</TableHeader>
              <TableHeader>Hyperfocus</TableHeader>
              <TableHeader>Novelty used</TableHeader>
              <TableHeader>Re-anchor</TableHeader>
            </tr>
          </thead>
          <tbody>
            {checkpoints.length === 0 ? (
              <tr><TableCell colSpan={9}>No checkpoints returned.</TableCell></tr>
            ) : (
              checkpoints.map((checkpoint) => {
                const totalNoveltyBudget = Number(checkpoint.budget_snapshot?.style_novelty_budget || 0);
                const noveltyRemaining = Number(checkpoint.novelty_budget_remaining || 0);
                const noveltyUsed = totalNoveltyBudget > 0 ? totalNoveltyBudget - noveltyRemaining : null;
                return (
                  <tr key={`${checkpoint.agent_id}:${checkpoint.trigger_id}:${checkpoint.checkpointed_at}`}>
                    <TableCell>
                      <div className="autonomy-strongCell">{checkpoint.agent_id}</div>
                      <div className="autonomy-subtleCell">{checkpoint.trigger_id}</div>
                    </TableCell>
                    <TableCell>
                      {checkpoint.run_id ? (
                        <div className="autonomy-inlineActions autonomy-inlineActions--table">
                          <span>{checkpoint.run_id}</span>
                          <ActionButton onClick={() => onOpenRun(checkpoint.run_id)} tone="secondary">Replay</ActionButton>
                        </div>
                      ) : (
                        "No run linked"
                      )}
                    </TableCell>
                    <TableCell>{formatLabel(checkpoint.status)}</TableCell>
                    <TableCell>{formatNumber(checkpoint.attempt, "0")}</TableCell>
                    <TableCell>{formatLabel(checkpoint.last_decision)}</TableCell>
                    <TableCell>{formatLabel(checkpoint.current_attention_mode)}</TableCell>
                    <TableCell>{formatNumber(checkpoint.hyperfocus_steps_used, "0")}</TableCell>
                    <TableCell>{noveltyUsed === null ? "Unavailable" : String(Math.max(0, noveltyUsed))}</TableCell>
                    <TableCell>{summarizeReanchor(checkpoint.last_reanchor_summary)}</TableCell>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
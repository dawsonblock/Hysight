import { formatLabel } from "@/features/autonomy/formatters";
import { ActionButton, PanelMessage, SectionHeader, StatusPill, TableCell, TableHeader } from "@/features/autonomy/components/ui";

export default function AutonomyRunsPanel({
  autonomyRuns,
  autonomyStatus,
  escalations,
  latestCheckpointByRun,
  onOpenRun,
  resourceErrors,
  selectedRunId,
}) {
  return (
    <section className="autonomy-panel">
      <SectionHeader
        title="Active autonomous runs"
        count={autonomyRuns.length}
        description="Inspect live autonomy run links and jump back into the existing replay surface."
      />
      {resourceErrors.runs ? <PanelMessage text={resourceErrors.runs} tone="error" /> : null}
      <div className="autonomy-tableWrap">
        <table className="autonomy-table">
          <thead>
            <tr>
              <TableHeader>Run</TableHeader>
              <TableHeader>Agent</TableHeader>
              <TableHeader>Trigger</TableHeader>
              <TableHeader>Run state</TableHeader>
              <TableHeader>Attention mode</TableHeader>
              <TableHeader>Last decision</TableHeader>
              <TableHeader>Checkpoint</TableHeader>
              <TableHeader>Escalation / block</TableHeader>
              <TableHeader>Replay</TableHeader>
            </tr>
          </thead>
          <tbody>
            {autonomyRuns.length === 0 ? (
              <tr><TableCell colSpan={9}>No active autonomous runs returned.</TableCell></tr>
            ) : (
              autonomyRuns.map((runRecord) => {
                const checkpoint = latestCheckpointByRun[runRecord.run_id];
                const runEscalation = escalations.find((item) => item.run_id === runRecord.run_id);
                const isSelectedRun = selectedRunId === runRecord.run_id;
                return (
                  <tr key={`${runRecord.agent_id}:${runRecord.trigger_id}:${runRecord.run_id}`}>
                    <TableCell>
                      <div className="autonomy-strongCell">{runRecord.run_id}</div>
                      <div className="autonomy-subtleCell">{runRecord.last_state || "In progress"}</div>
                    </TableCell>
                    <TableCell>{runRecord.agent_id}</TableCell>
                    <TableCell>{runRecord.trigger_id}</TableCell>
                    <TableCell>{formatLabel(runRecord.run_status)}</TableCell>
                    <TableCell>{formatLabel(checkpoint?.current_attention_mode)}</TableCell>
                    <TableCell>{formatLabel(checkpoint?.last_decision || autonomyStatus?.last_evaluator_decision)}</TableCell>
                    <TableCell>{formatLabel(checkpoint?.status)}</TableCell>
                    <TableCell>
                      <StatusPill
                        tone={autonomyStatus?.kill_switch_active ? "danger" : runEscalation ? "warning" : "neutral"}
                        value={autonomyStatus?.kill_switch_active ? "Kill switch active" : runEscalation ? "Escalated" : "Clear"}
                      />
                    </TableCell>
                    <TableCell>
                      <ActionButton onClick={() => onOpenRun(runRecord.run_id)} tone={isSelectedRun ? "success" : "secondary"}>
                        {isSelectedRun ? "Viewing in Runs" : "Open run replay"}
                      </ActionButton>
                    </TableCell>
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
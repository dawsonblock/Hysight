import { formatLabel, formatTimestamp } from "@/features/autonomy/formatters";
import { ActionButton, PanelMessage, SectionHeader, TableCell, TableHeader } from "@/features/autonomy/components/ui";

export default function EscalationsPanel({ escalations, onOpenRun, resourceError }) {
  return (
    <section className="autonomy-panel">
      <SectionHeader
        title="Escalations"
        count={escalations.length}
        description="Pending autonomy escalations linked back to ordinary run replay."
      />
      {resourceError ? <PanelMessage text={resourceError} tone="error" /> : null}
      <div className="autonomy-tableWrap">
        <table className="autonomy-table">
          <thead>
            <tr>
              <TableHeader>Reason / status</TableHeader>
              <TableHeader>Agent</TableHeader>
              <TableHeader>Run</TableHeader>
              <TableHeader>Action class</TableHeader>
              <TableHeader>Created</TableHeader>
              <TableHeader>Replay</TableHeader>
            </tr>
          </thead>
          <tbody>
            {escalations.length === 0 ? (
              <tr><TableCell colSpan={6}>No escalations returned.</TableCell></tr>
            ) : (
              escalations.map((escalation) => (
                <tr key={`${escalation.agent_id}:${escalation.trigger_id}`}>
                  <TableCell>
                    <div className="autonomy-strongCell">{formatLabel(escalation.status)}</div>
                    <div className="autonomy-subtleCell">{formatLabel(escalation.last_decision)}</div>
                  </TableCell>
                  <TableCell>{escalation.agent_id}</TableCell>
                  <TableCell>{escalation.run_id || "No linked run"}</TableCell>
                  <TableCell>Unavailable</TableCell>
                  <TableCell>{formatTimestamp(escalation.checkpointed_at)}</TableCell>
                  <TableCell>
                    {escalation.run_id ? (
                      <ActionButton onClick={() => onOpenRun(escalation.run_id)} tone="secondary">Open replay</ActionButton>
                    ) : (
                      <span className="autonomy-subtleCell">No run link</span>
                    )}
                  </TableCell>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
import { formatLabel, formatTimestamp, payloadPreview } from "@/features/autonomy/formatters";
import { ActionButton, PanelMessage, SectionHeader, StatusPill, TableCell, TableHeader } from "@/features/autonomy/components/ui";

export default function InboxPanel({
  actionKey,
  agents,
  formError,
  inboxForm,
  inboxItems,
  onCancel,
  onCreateInboxItem,
  onInboxFormChange,
  resourceError,
}) {
  return (
    <section className="autonomy-panel">
      <SectionHeader
        title="Inbox"
        count={inboxItems.length}
        description="Queue or cancel backend inbox work for bounded agents."
      />
      {resourceError ? <PanelMessage text={resourceError} tone="error" /> : null}
      <div className="autonomy-tableWrap">
        <table className="autonomy-table">
          <thead>
            <tr>
              <TableHeader>Item</TableHeader>
              <TableHeader>Agent</TableHeader>
              <TableHeader>Goal</TableHeader>
              <TableHeader>Payload</TableHeader>
              <TableHeader>Status</TableHeader>
              <TableHeader>Created</TableHeader>
              <TableHeader>Actions</TableHeader>
            </tr>
          </thead>
          <tbody>
            {inboxItems.length === 0 ? (
              <tr><TableCell colSpan={7}>No inbox items returned.</TableCell></tr>
            ) : (
              inboxItems.map((item) => (
                <tr key={item.item_id}>
                  <TableCell>
                    <div className="autonomy-strongCell">{item.item_id}</div>
                    <div className="autonomy-subtleCell">Claimed: {formatTimestamp(item.claimed_at)}</div>
                  </TableCell>
                  <TableCell>{item.agent_id}</TableCell>
                  <TableCell>{item.goal}</TableCell>
                  <TableCell>{payloadPreview(item.payload)}</TableCell>
                  <TableCell>
                    <StatusPill
                      tone={item.status === "queued" ? "warning" : item.status === "claimed" ? "neutral" : "danger"}
                      value={formatLabel(item.status)}
                    />
                  </TableCell>
                  <TableCell>{formatTimestamp(item.created_at)}</TableCell>
                  <TableCell>
                    <ActionButton busy={actionKey === `cancel-inbox:${item.item_id}`} disabled={item.status === "cancelled"} onClick={() => onCancel(item)} tone="danger">
                      Cancel
                    </ActionButton>
                  </TableCell>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <form className="autonomy-form" onSubmit={onCreateInboxItem}>
        <div className="autonomy-formTitle">Enqueue inbox item</div>
        <div className="autonomy-formGrid autonomy-formGrid--three">
          <label className="autonomy-field">
            <span className="autonomy-fieldLabel">Agent</span>
            <select className="autonomy-select" onChange={(event) => onInboxFormChange("agentId", event.target.value)} value={inboxForm.agentId}>
              <option value="">Select agent</option>
              {agents.map((agent) => (
                <option key={agent.agent_id} label={`${agent.name} (${agent.agent_id})`} value={agent.agent_id} />
              ))}
            </select>
          </label>
          <label className="autonomy-field autonomy-field--wide">
            <span className="autonomy-fieldLabel">Goal</span>
            <input className="autonomy-input" onChange={(event) => onInboxFormChange("goal", event.target.value)} value={inboxForm.goal} />
          </label>
          <label className="autonomy-field autonomy-field--wide">
            <span className="autonomy-fieldLabel">Payload JSON</span>
            <textarea className="autonomy-textarea" onChange={(event) => onInboxFormChange("payload", event.target.value)} rows={4} value={inboxForm.payload} />
          </label>
        </div>
        {formError ? <PanelMessage text={formError} tone="error" /> : null}
        <div className="autonomy-formActions">
          <ActionButton busy={actionKey === "create-inbox"} type="submit" tone="success">Queue inbox work</ActionButton>
        </div>
      </form>
    </section>
  );
}
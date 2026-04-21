import { formatTimestamp, payloadPreview } from "@/features/autonomy/formatters";
import { ActionButton, PanelMessage, SectionHeader, StatusPill, TableCell, TableHeader } from "@/features/autonomy/components/ui";

export default function SchedulesPanel({
  actionKey,
  agents,
  formError,
  onCreateSchedule,
  onDisable,
  onEnable,
  onScheduleFormChange,
  resourceError,
  scheduleForm,
  schedules,
}) {
  return (
    <section className="autonomy-panel">
      <SectionHeader
        title="Schedules"
        count={schedules.length}
        description="Enable and disable backend schedule bindings without leaving the operator shell."
      />
      {resourceError ? <PanelMessage text={resourceError} tone="error" /> : null}
      <div className="autonomy-tableWrap">
        <table className="autonomy-table">
          <thead>
            <tr>
              <TableHeader>Schedule</TableHeader>
              <TableHeader>Agent</TableHeader>
              <TableHeader>Interval</TableHeader>
              <TableHeader>Goal override</TableHeader>
              <TableHeader>State</TableHeader>
              <TableHeader>Last fired</TableHeader>
              <TableHeader>Actions</TableHeader>
            </tr>
          </thead>
          <tbody>
            {schedules.length === 0 ? (
              <tr><TableCell colSpan={7}>No schedules returned.</TableCell></tr>
            ) : (
              schedules.map((schedule) => (
                <tr key={schedule.schedule_id}>
                  <TableCell>
                    <div className="autonomy-strongCell">{schedule.schedule_id}</div>
                    <div className="autonomy-subtleCell">{payloadPreview(schedule.payload)}</div>
                  </TableCell>
                  <TableCell>{schedule.agent_id}</TableCell>
                  <TableCell>{schedule.interval_seconds}s</TableCell>
                  <TableCell>{schedule.goal_override || "No override"}</TableCell>
                  <TableCell>
                    <StatusPill tone={schedule.enabled ? "success" : "danger"} value={schedule.enabled ? "Enabled" : "Disabled"} />
                  </TableCell>
                  <TableCell>{formatTimestamp(schedule.last_fired_at)}</TableCell>
                  <TableCell>
                    <div className="autonomy-inlineActions autonomy-inlineActions--table">
                      <ActionButton busy={actionKey === `enable-schedule:${schedule.schedule_id}`} disabled={schedule.enabled} onClick={() => onEnable(schedule)} tone="success">
                        Enable
                      </ActionButton>
                      <ActionButton busy={actionKey === `disable-schedule:${schedule.schedule_id}`} disabled={!schedule.enabled} onClick={() => onDisable(schedule)} tone="danger">
                        Disable
                      </ActionButton>
                    </div>
                  </TableCell>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <form className="autonomy-form" onSubmit={onCreateSchedule}>
        <div className="autonomy-formTitle">Create schedule</div>
        <div className="autonomy-formGrid autonomy-formGrid--three">
          <label className="autonomy-field">
            <span className="autonomy-fieldLabel">Agent</span>
            <select className="autonomy-select" onChange={(event) => onScheduleFormChange("agentId", event.target.value)} value={scheduleForm.agentId}>
              <option value="">Select agent</option>
              {agents.map((agent) => (
                <option key={agent.agent_id} label={`${agent.name} (${agent.agent_id})`} value={agent.agent_id} />
              ))}
            </select>
          </label>
          <label className="autonomy-field">
            <span className="autonomy-fieldLabel">Interval seconds</span>
            <input className="autonomy-input" min="1" onChange={(event) => onScheduleFormChange("intervalSeconds", event.target.value)} type="number" value={scheduleForm.intervalSeconds} />
          </label>
          <label className="autonomy-field">
            <span className="autonomy-fieldLabel">Goal override</span>
            <input className="autonomy-input" onChange={(event) => onScheduleFormChange("goalOverride", event.target.value)} value={scheduleForm.goalOverride} />
          </label>
          <label className="autonomy-field autonomy-field--wide">
            <span className="autonomy-fieldLabel">Payload JSON</span>
            <textarea className="autonomy-textarea" onChange={(event) => onScheduleFormChange("payload", event.target.value)} rows={4} value={scheduleForm.payload} />
          </label>
        </div>
        <label className="autonomy-checkbox">
          <input checked={scheduleForm.enabled} onChange={(event) => onScheduleFormChange("enabled", event.target.checked)} type="checkbox" />
          Enabled on create
        </label>
        {formError ? <PanelMessage text={formError} tone="error" /> : null}
        <div className="autonomy-formActions">
          <ActionButton busy={actionKey === "create-schedule"} type="submit" tone="success">Create schedule</ActionButton>
        </div>
      </form>
    </section>
  );
}
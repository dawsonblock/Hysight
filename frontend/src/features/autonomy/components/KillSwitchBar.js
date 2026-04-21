import { formatTimestamp } from "@/features/autonomy/formatters";
import { ActionButton, SectionHeader, StatusPill } from "@/features/autonomy/components/ui";

export default function KillSwitchBar({ actionKey, autonomyStatus, killReason, onKillReasonChange, onSetKillSwitch }) {
  return (
    <section className="autonomy-panel autonomy-panel--kill">
      <SectionHeader
        title="Kill switch"
        description="Real backend safety control. The UI waits for backend confirmation before showing success."
      />
      <div className="autonomy-killBar">
        <div className="autonomy-killSummary">
          <StatusPill
            tone={autonomyStatus?.kill_switch_active ? "danger" : "success"}
            value={autonomyStatus?.kill_switch_active ? "Kill switch active" : "Kill switch clear"}
          />
          <div className="autonomy-killMeta">
            <div>Reason: {autonomyStatus?.kill_switch_reason || "No active kill-switch reason."}</div>
            <div>Set at: {formatTimestamp(autonomyStatus?.kill_switch_set_at)}</div>
          </div>
        </div>
        <div className="autonomy-killControls">
          <label className="autonomy-field autonomy-field--wide">
            <span className="autonomy-fieldLabel">Kill reason</span>
            <input
              className="autonomy-input"
              onChange={(event) => onKillReasonChange(event.target.value)}
              placeholder="Operator reason recorded with kill-switch activation"
              value={killReason}
            />
          </label>
          <div className="autonomy-inlineActions">
            <ActionButton
              busy={actionKey === "kill"}
              disabled={autonomyStatus?.kill_switch_active}
              onClick={() => onSetKillSwitch(true)}
              tone="danger"
            >
              Kill autonomy
            </ActionButton>
            <ActionButton
              busy={actionKey === "unkill"}
              disabled={!autonomyStatus?.kill_switch_active}
              onClick={() => onSetKillSwitch(false)}
              tone="success"
            >
              Clear kill switch
            </ActionButton>
          </div>
        </div>
      </div>
    </section>
  );
}
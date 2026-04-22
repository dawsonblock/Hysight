import { useState } from "react";
import { formatTimestamp } from "@/features/autonomy/formatters";
import { ActionButton, SectionHeader, StatusPill } from "@/features/autonomy/components/ui";
import KillSwitchConfirmDialog from "@/features/autonomy/components/KillSwitchConfirmDialog";

export default function KillSwitchBar({ actionKey, autonomyStatus, killReason, onSetKillSwitch, setKillReason }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [pendingActive, setPendingActive] = useState(false);

  function openDialog(nextActive) {
    setPendingActive(nextActive);
    setKillReason("");
    setDialogOpen(true);
  }

  function handleConfirm() {
    setDialogOpen(false);
    onSetKillSwitch(pendingActive, killReason.trim() || null);
  }

  function handleCancel() {
    setDialogOpen(false);
  }

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
          <div className="autonomy-inlineActions">
            <ActionButton
              busy={actionKey === "kill"}
              disabled={autonomyStatus?.kill_switch_active}
              onClick={() => openDialog(true)}
              tone="danger"
            >
              Kill autonomy
            </ActionButton>
            <ActionButton
              busy={actionKey === "unkill"}
              disabled={!autonomyStatus?.kill_switch_active}
              onClick={() => openDialog(false)}
              tone="success"
            >
              Clear kill switch
            </ActionButton>
          </div>
        </div>
      </div>
      <KillSwitchConfirmDialog
        open={dialogOpen}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
        nextActive={pendingActive}
        reason={killReason}
        onReasonChange={setKillReason}
      />
    </section>
  );
}
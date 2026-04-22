import "@/features/autonomy/AutonomyWorkspace.css";
import AgentsPanel from "@/features/autonomy/components/AgentsPanel";
import AutonomyRunsPanel from "@/features/autonomy/components/AutonomyRunsPanel";
import AutonomyStatusHeader from "@/features/autonomy/components/AutonomyStatusHeader";
import BudgetPanel from "@/features/autonomy/components/BudgetPanel";
import CheckpointsPanel from "@/features/autonomy/components/CheckpointsPanel";
import EscalationsPanel from "@/features/autonomy/components/EscalationsPanel";
import InboxPanel from "@/features/autonomy/components/InboxPanel";
import KillSwitchBar from "@/features/autonomy/components/KillSwitchBar";
import SchedulesPanel from "@/features/autonomy/components/SchedulesPanel";
import SelectedRunPanel from "@/features/autonomy/components/SelectedRunPanel";
import StyleStatePanel from "@/features/autonomy/components/StyleStatePanel";
import {
  formatTimestamp,
} from "@/features/autonomy/formatters";
import { ActionButton, PanelMessage } from "@/features/autonomy/components/ui";
import useAutonomyWorkspaceController from "@/features/autonomy/useAutonomyWorkspaceController";

export default function AutonomyWorkspace({ onOpenRun, selectedRunId }) {
  const {
    actionKey,
    actionNotice,
    activeRunCountByAgent,
    agentForm,
    agents,
    autonomyRuns,
    autonomyStatus,
    budgetByAgent,
    budgets,
    checkpoints,
    degradedResourceKeys,
    escalations,
    escalationCountByAgent,
    formErrors,
    handleAgentFormChange,
    handleCancelInboxItem,
    handleCreateAgent,
    handleCreateInboxItem,
    handleCreateSchedule,
    handleDisableSchedule,
    handleEnableSchedule,
    handleInboxFormChange,
    handleKillSwitchChange,
    handlePauseAgent,
    handleResumeAgent,
    handleScheduleFormChange,
    handleStopAgent,
    inboxForm,
    inboxItems,
    isStaleData,
    killReason,
    lastAttemptedSyncAt,
    lastSuccessfulSyncAt,
    latestCheckpointByAgent,
    latestCheckpointByRun,
    loading,
    refreshWorkspace,
    refreshing,
    resourceErrors,
    scheduleForm,
    schedules,
    selectedRunSummary,
    setKillReason,
    supervisorTone,
  } = useAutonomyWorkspaceController({ selectedRunId });

  const degradedResourcesLabel = degradedResourceKeys
    .slice(0, 3)
    .map((resourceKey) => resourceKey)
    .join(", ");
  const additionalDegradedResources = degradedResourceKeys.length > 3
    ? `, and ${degradedResourceKeys.length - 3} more`
    : "";
  const hasSuccessfulSync = Boolean(lastSuccessfulSyncAt);
  const refreshMetaText = refreshing
    ? "Refreshing…"
    : degradedResourceKeys.length > 0
      ? `Last successful sync ${formatTimestamp(lastSuccessfulSyncAt, "Not loaded yet")} • Last attempt ${formatTimestamp(lastAttemptedSyncAt, "Unavailable")}`
      : `Last successful sync ${formatTimestamp(lastSuccessfulSyncAt, "Not loaded yet")}`;
  const workspaceStatusNotice = degradedResourceKeys.length > 0
    ? {
        tone: hasSuccessfulSync ? (isStaleData ? "error" : "warning") : "error",
        text: hasSuccessfulSync
          ? `Degraded backend state for ${degradedResourcesLabel}${additionalDegradedResources}. Showing retained data from ${formatTimestamp(lastSuccessfulSyncAt)} where available.`
          : `Autonomy backend load failed for ${degradedResourcesLabel}${additionalDegradedResources}. No successful sync is available yet.`,
      }
    : isStaleData
      ? {
          tone: "warning",
          text: `Autonomy data is stale. Last successful sync ${formatTimestamp(lastSuccessfulSyncAt, "Unavailable")}.`,
        }
      : null;

  return (
    <section className="autonomy-workspace">
      <div className="autonomy-workspaceHeader">
        <div>
          <div className="workspace-eyebrow">Bounded autonomy control plane</div>
          <h2 className="workspace-title">Inspect and control the backend supervisor without leaving the operator shell.</h2>
          <p className="workspace-description">
            This workspace shows backend-reported autonomy status, bounded operator-style control state, and control actions.
            It does not execute autonomy logic in the browser.
          </p>
        </div>

        <div className="autonomy-workspaceControls">
          <div className="autonomy-refreshMeta">
            {refreshMetaText}
          </div>
          <ActionButton
            busy={actionKey === "refresh"}
            onClick={refreshWorkspace}
            tone="secondary"
          >
            Refresh now
          </ActionButton>
        </div>
      </div>

      {actionNotice ? <PanelMessage text={actionNotice.text} tone={actionNotice.tone} /> : null}
      {workspaceStatusNotice ? <PanelMessage text={workspaceStatusNotice.text} tone={workspaceStatusNotice.tone} /> : null}

      <AutonomyStatusHeader
        autonomyStatus={autonomyStatus}
        budgets={budgets}
        loading={loading}
        resourceError={resourceErrors.status}
        supervisorTone={supervisorTone}
      />

      <KillSwitchBar
        actionKey={actionKey}
        autonomyStatus={autonomyStatus}
        killReason={killReason}
        onSetKillSwitch={handleKillSwitchChange}
        setKillReason={setKillReason}
      />

      <div className="autonomy-grid autonomy-grid--twoColumn">
        <AgentsPanel
          actionKey={actionKey}
          activeRunCountByAgent={activeRunCountByAgent}
          agentForm={agentForm}
          agents={agents}
          autonomyStatus={autonomyStatus}
          budgetByAgent={budgetByAgent}
          escalationCountByAgent={escalationCountByAgent}
          formError={formErrors.agent}
          latestCheckpointByAgent={latestCheckpointByAgent}
          onAgentFormChange={handleAgentFormChange}
          onCreateAgent={handleCreateAgent}
          onPause={handlePauseAgent}
          onResume={handleResumeAgent}
          onStop={handleStopAgent}
          resourceError={resourceErrors.agents}
        />

        <SchedulesPanel
          actionKey={actionKey}
          agents={agents}
          formError={formErrors.schedule}
          onCreateSchedule={handleCreateSchedule}
          onDisable={handleDisableSchedule}
          onEnable={handleEnableSchedule}
          onScheduleFormChange={handleScheduleFormChange}
          resourceError={resourceErrors.schedules}
          scheduleForm={scheduleForm}
          schedules={schedules}
        />
      </div>

      <div className="autonomy-grid autonomy-grid--twoColumn">
        <InboxPanel
          actionKey={actionKey}
          agents={agents}
          formError={formErrors.inbox}
          inboxForm={inboxForm}
          inboxItems={inboxItems}
          onCancel={handleCancelInboxItem}
          onCreateInboxItem={handleCreateInboxItem}
          onInboxFormChange={handleInboxFormChange}
          resourceError={resourceErrors.inbox}
        />

        <AutonomyRunsPanel
          autonomyRuns={autonomyRuns}
          autonomyStatus={autonomyStatus}
          escalations={escalations}
          latestCheckpointByRun={latestCheckpointByRun}
          onOpenRun={onOpenRun}
          resourceErrors={{ runs: resourceErrors.runs }}
          selectedRunId={selectedRunId}
        />
      </div>

      <div className="autonomy-grid autonomy-grid--threeColumn">
        <EscalationsPanel
          escalations={escalations}
          onOpenRun={onOpenRun}
          resourceError={resourceErrors.escalations}
        />

        <BudgetPanel
          autonomyStatus={autonomyStatus}
          budgets={budgets}
          resourceError={resourceErrors.budgets}
        />

        <StyleStatePanel
          agents={agents}
          autonomyStatus={autonomyStatus}
          latestCheckpointByAgent={latestCheckpointByAgent}
        />
      </div>

      <CheckpointsPanel
        checkpoints={checkpoints}
        onOpenRun={onOpenRun}
        resourceError={resourceErrors.checkpoints}
      />

      <SelectedRunPanel selectedRunSummary={selectedRunSummary} />
    </section>
  );
}
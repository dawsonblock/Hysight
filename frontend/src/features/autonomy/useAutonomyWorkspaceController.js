import { useState } from "react";
import { buildCountMap, latestBy } from "@/features/autonomy/formatters";
import useAutonomyPolling from "@/features/autonomy/useAutonomyPolling";
import useAutonomyActions from "@/features/autonomy/useAutonomyActions";
import useAutonomyForms from "@/features/autonomy/useAutonomyForms";
import useAutonomyRunSummaries from "@/features/autonomy/useAutonomyRunSummaries";

export default function useAutonomyWorkspaceController({ selectedRunId }) {
  const [killReason, setKillReason] = useState("");
  const {
    resourceData,
    resourceErrors,
    loading,
    refreshing,
    degradedResourceKeys,
    isStaleData,
    lastAttemptedSyncAt,
    lastSuccessfulSyncAt,
    refreshWorkspace,
  } = useAutonomyPolling();

  const agents = resourceData.agents;
  const schedules = resourceData.schedules;
  const inboxItems = resourceData.inbox;
  const autonomyRuns = resourceData.runs;
  const checkpoints = resourceData.checkpoints;
  const budgets = resourceData.budgets;
  const escalations = resourceData.escalations;
  const autonomyStatus = resourceData.status;

  const {
    actionKey,
    actionNotice,
    performAction,
    handleKillSwitchChange,
    handlePauseAgent,
    handleResumeAgent,
    handleStopAgent,
    handleEnableSchedule,
    handleDisableSchedule,
    handleCancelInboxItem,
  } = useAutonomyActions({ refreshWorkspace });

  const {
    formErrors,
    agentForm,
    scheduleForm,
    inboxForm,
    handleAgentFormChange,
    handleScheduleFormChange,
    handleInboxFormChange,
    handleCreateAgent,
    handleCreateSchedule,
    handleCreateInboxItem,
  } = useAutonomyForms({ agents, performAction });

  const activeRunIds = autonomyRuns.map((r) => r.run_id);
  const { selectedRunSummary, runSummaries, runSummariesError } = useAutonomyRunSummaries({ selectedRunId, activeRunIds });

  const latestCheckpointByAgent = latestBy(
    checkpoints,
    (checkpoint) => checkpoint.agent_id,
    (checkpoint) => checkpoint.checkpointed_at
  );
  const latestCheckpointByRun = latestBy(
    checkpoints.filter((checkpoint) => checkpoint.run_id),
    (checkpoint) => checkpoint.run_id,
    (checkpoint) => checkpoint.checkpointed_at
  );
  const escalationCountByAgent = buildCountMap(
    escalations,
    (escalation) => escalation.agent_id
  );
  const activeRunCountByAgent = buildCountMap(
    autonomyRuns,
    (runRecord) => runRecord.agent_id
  );
  const budgetByAgent = budgets.reduce((accumulator, ledger) => {
    accumulator[ledger.agent_id] = ledger;
    return accumulator;
  }, {});

  const supervisorTone = autonomyStatus?.kill_switch_active
    ? "danger"
    : (autonomyStatus?.pending_escalations || 0) > 0
      ? "warning"
      : autonomyStatus?.running
        ? "success"
        : "neutral";

  return {
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
    resourceErrors: { ...resourceErrors, runSummaries: runSummariesError },
    runSummaries,
    scheduleForm,
    schedules,
    selectedRunSummary,
    setKillReason,
    supervisorTone,
  };
}

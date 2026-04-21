import { useEffect, useRef, useState } from "react";
import { getRunSummary, toErrorMessage } from "@/lib/api";
import {
  cancelAutonomyInboxItem,
  clearAutonomyKillSwitch,
  createAutonomyAgent,
  createAutonomyInboxItem,
  createAutonomySchedule,
  disableAutonomySchedule,
  enableAutonomyKillSwitch,
  enableAutonomySchedule,
  getAutonomyStatus,
  listAutonomyAgents,
  listAutonomyBudgets,
  listAutonomyCheckpoints,
  listAutonomyEscalations,
  listAutonomyInbox,
  listAutonomyRuns,
  listAutonomySchedules,
  pauseAutonomyAgent,
  resumeAutonomyAgent,
  stopAutonomyAgent,
} from "@/lib/autonomy-api";
import {
  buildCountMap,
  latestBy,
  parseJsonInput,
} from "@/features/autonomy/formatters";
import { toast } from "@/hooks/use-toast";

const POLL_INTERVAL_MS = 15000;
const STALE_SYNC_THRESHOLD_MS = POLL_INTERVAL_MS * 2;

const EMPTY_ERRORS = {
  status: "",
  agents: "",
  schedules: "",
  inbox: "",
  runs: "",
  checkpoints: "",
  budgets: "",
  escalations: "",
  runSummaries: "",
};

const EMPTY_DATA = {
  status: null,
  agents: [],
  schedules: [],
  inbox: [],
  runs: [],
  checkpoints: [],
  budgets: [],
  escalations: [],
  runSummaries: {},
};

const INITIAL_AGENT_FORM = {
  name: "",
  description: "",
  styleProfileId: "conservative_operator",
  enabled: true,
  maxStepsPerRun: "50",
  maxRunsPerAgent: "25",
  maxParallelRuns: "1",
  maxRetriesPerStep: "2",
  maxRunDurationSeconds: "900",
  deadmanTimeoutSeconds: "1800",
  allowMemoryWrites: true,
  allowExternalWrites: false,
  autoResumeAfterApproval: false,
};

const INITIAL_SCHEDULE_FORM = {
  agentId: "",
  intervalSeconds: "300",
  goalOverride: "",
  payload: "{}",
  enabled: true,
};

const INITIAL_INBOX_FORM = {
  agentId: "",
  goal: "",
  payload: "{}",
};

function mergeRunSummaries(currentRunSummaries, mergedRuns, nextRunSummaries) {
  const runSummaryMap = {};

  mergedRuns
    .map((runRecord) => runRecord.run_id)
    .filter(Boolean)
    .forEach((runId) => {
      if (Object.prototype.hasOwnProperty.call(nextRunSummaries, runId)) {
        runSummaryMap[runId] = nextRunSummaries[runId];
      } else if (Object.prototype.hasOwnProperty.call(currentRunSummaries, runId)) {
        runSummaryMap[runId] = currentRunSummaries[runId];
      }
    });

  return runSummaryMap;
}

export default function useAutonomyWorkspaceController({ selectedRunId }) {
  const loadCancelledRef = useRef(false);
  const requestStateRef = useRef({
    inFlight: false,
    queued: false,
    queuedIsPolling: true,
  });
  const requestWorkspaceLoadRef = useRef(null);
  const hasLoadedOnceRef = useRef(false);

  const [resourceData, setResourceData] = useState(EMPTY_DATA);
  const [resourceErrors, setResourceErrors] = useState(EMPTY_ERRORS);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastAttemptedSyncAt, setLastAttemptedSyncAt] = useState(null);
  const [lastSuccessfulSyncAt, setLastSuccessfulSyncAt] = useState(null);
  const [actionKey, setActionKey] = useState("");
  const [actionNotice, setActionNotice] = useState(
    /** @type {{ tone: string, text: string } | null} */ (null)
  );
  const [killReason, setKillReason] = useState("");
  const [formErrors, setFormErrors] = useState({ agent: "", schedule: "", inbox: "" });
  const [agentForm, setAgentForm] = useState(INITIAL_AGENT_FORM);
  const [scheduleForm, setScheduleForm] = useState(INITIAL_SCHEDULE_FORM);
  const [inboxForm, setInboxForm] = useState(INITIAL_INBOX_FORM);

  const agents = resourceData.agents;
  const schedules = resourceData.schedules;
  const inboxItems = resourceData.inbox;
  const autonomyRuns = resourceData.runs;
  const checkpoints = resourceData.checkpoints;
  const budgets = resourceData.budgets;
  const escalations = resourceData.escalations;
  const autonomyStatus = resourceData.status;
  const runSummaries = resourceData.runSummaries;

  useEffect(() => {
    if (!agents.length) {
      return;
    }

    setScheduleForm((currentValue) =>
      currentValue.agentId
        ? currentValue
        : { ...currentValue, agentId: agents[0].agent_id }
    );
    setInboxForm((currentValue) =>
      currentValue.agentId
        ? currentValue
        : { ...currentValue, agentId: agents[0].agent_id }
    );
  }, [agents]);

  async function loadWorkspaceOnce(isPolling = false) {
    const attemptStartedAt = new Date().toISOString();
    setLastAttemptedSyncAt(attemptStartedAt);

    if (!hasLoadedOnceRef.current && !isPolling) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }

    const loaderEntries = [
      ["status", getAutonomyStatus],
      ["agents", listAutonomyAgents],
      ["schedules", listAutonomySchedules],
      ["inbox", () => listAutonomyInbox()],
      ["runs", listAutonomyRuns],
      ["checkpoints", () => listAutonomyCheckpoints()],
      ["budgets", listAutonomyBudgets],
      ["escalations", listAutonomyEscalations],
    ];

    const settledResources = await Promise.allSettled(
      loaderEntries.map(([, loader]) => Promise.resolve().then(() => loader()))
    );

    if (loadCancelledRef.current) {
      return;
    }

    const nextErrors = { ...EMPTY_ERRORS };
    const nextValues = {};
    let successfulResourceCount = 0;

    loaderEntries.forEach(([resourceKey], index) => {
      const result = settledResources[index];

      if (result.status === "fulfilled") {
        successfulResourceCount += 1;
        if (resourceKey === "status") {
          nextValues.status = result.value;
        } else if (resourceKey === "agents") {
          nextValues.agents = result.value.agents || [];
        } else if (resourceKey === "schedules") {
          nextValues.schedules = result.value.schedules || [];
        } else if (resourceKey === "inbox") {
          nextValues.inbox = result.value.items || [];
        } else if (resourceKey === "runs") {
          nextValues.runs = result.value.runs || [];
        } else if (resourceKey === "checkpoints") {
          nextValues.checkpoints = result.value.checkpoints || [];
        } else if (resourceKey === "budgets") {
          nextValues.budgets = result.value.ledgers || [];
        } else if (resourceKey === "escalations") {
          nextValues.escalations = result.value.escalations || [];
        }
      } else {
        nextErrors[resourceKey] = toErrorMessage(
          result.reason,
          `Unable to load ${resourceKey}.`
        );
      }
    });

    const nextRunRecords = nextValues.runs || [];
    const runIds = Array.from(
      new Set(nextRunRecords.map((runRecord) => runRecord.run_id).filter(Boolean))
    );

    const nextRunSummaries = {};
    if (runIds.length > 0) {
      const settledSummaries = await Promise.allSettled(
        runIds.map((runId) => getRunSummary(runId))
      );

      if (loadCancelledRef.current) {
        return;
      }

      let summaryFailureCount = 0;
      settledSummaries.forEach((result, index) => {
        const runId = runIds[index];
        if (result.status === "fulfilled") {
          nextRunSummaries[runId] = result.value;
        } else {
          summaryFailureCount += 1;
        }
      });

      if (summaryFailureCount > 0) {
        nextErrors.runSummaries = `${summaryFailureCount} autonomy run detail request${
          summaryFailureCount === 1 ? "" : "s"
        } failed.`;
      }
    }

    const completedAt = new Date().toISOString();

    setResourceData((currentValue) => {
      const mergedRuns = nextValues.runs || currentValue.runs;
      return {
        ...currentValue,
        ...nextValues,
        runSummaries: mergeRunSummaries(
          currentValue.runSummaries,
          mergedRuns,
          nextRunSummaries
        ),
      };
    });
    setResourceErrors(nextErrors);
    hasLoadedOnceRef.current = true;
    setLoading(false);
    setRefreshing(false);

    if (successfulResourceCount > 0) {
      setLastSuccessfulSyncAt(completedAt);
    }
  }

  async function requestWorkspaceLoad(isPolling = false) {
    if (loadCancelledRef.current) {
      return;
    }

    const requestState = requestStateRef.current;

    if (requestState.inFlight) {
      requestState.queued = true;
      requestState.queuedIsPolling = requestState.queuedIsPolling && isPolling;
      return;
    }

    requestState.inFlight = true;
    let nextIsPolling = isPolling;

    try {
      do {
        requestState.queued = false;
        requestState.queuedIsPolling = true;
        await loadWorkspaceOnce(nextIsPolling);
        nextIsPolling = requestState.queuedIsPolling;
      } while (requestState.queued && !loadCancelledRef.current);
    } finally {
      requestState.inFlight = false;
    }
  }

  requestWorkspaceLoadRef.current = requestWorkspaceLoad;

  useEffect(() => {
    const requestState = requestStateRef.current;

    loadCancelledRef.current = false;
    requestWorkspaceLoadRef.current?.(false);

    const intervalId = window.setInterval(() => {
      requestWorkspaceLoadRef.current?.(true);
    }, POLL_INTERVAL_MS);

    return () => {
      loadCancelledRef.current = true;
      requestState.inFlight = false;
      requestState.queued = false;
      requestState.queuedIsPolling = true;
      window.clearInterval(intervalId);
    };
  }, []);

  async function performAction(key, operation, successTitle, successDescription) {
    setActionKey(key);
    setActionNotice(null);

    try {
      await operation();
      setActionNotice({ tone: "success", text: successDescription });
      toast({ title: successTitle, description: successDescription });
      requestWorkspaceLoadRef.current?.(false);
    } catch (error) {
      const message = toErrorMessage(error, "Action failed.");
      setActionNotice({ tone: "error", text: message });
      toast({ title: successTitle, description: message });
    } finally {
      setActionKey("");
    }
  }

  async function handleKillSwitchChange(nextActive) {
    const confirmationMessage = nextActive
      ? "Confirm kill switch activation. This blocks new and continued bounded autonomy until the backend clears it."
      : "Confirm kill switch clear. This allows bounded autonomy to resume under backend policy controls.";

    if (!window.confirm(confirmationMessage)) {
      return;
    }

    await performAction(
      nextActive ? "kill" : "unkill",
      () =>
        nextActive
          ? enableAutonomyKillSwitch({ reason: killReason.trim() || null })
          : clearAutonomyKillSwitch(),
      nextActive ? "Kill switch updated" : "Kill switch cleared",
      nextActive
        ? "Autonomy kill switch is now active."
        : "Autonomy kill switch is now clear."
    );
  }

  async function handleCreateAgent(event) {
    event.preventDefault();
    setFormErrors((currentValue) => ({ ...currentValue, agent: "" }));

    const trimmedName = agentForm.name.trim();
    if (!trimmedName) {
      setFormErrors((currentValue) => ({
        ...currentValue,
        agent: "Agent name is required.",
      }));
      return;
    }

    const payload = {
      name: trimmedName,
      description: agentForm.description.trim() || null,
      mode: "bounded",
      style_profile_id: agentForm.styleProfileId.trim() || "conservative_operator",
      policy: {
        mode: "bounded",
        enabled: agentForm.enabled,
        budget: {
          max_steps_per_run: Number(agentForm.maxStepsPerRun),
          max_runs_per_agent: Number(agentForm.maxRunsPerAgent),
          max_parallel_runs: Number(agentForm.maxParallelRuns),
          max_retries_per_step: Number(agentForm.maxRetriesPerStep),
          max_run_duration_seconds: Number(agentForm.maxRunDurationSeconds),
          deadman_timeout_seconds: Number(agentForm.deadmanTimeoutSeconds),
        },
        allow_memory_writes: agentForm.allowMemoryWrites,
        allow_external_writes: agentForm.allowExternalWrites,
        auto_resume_after_approval: agentForm.autoResumeAfterApproval,
      },
    };

    await performAction(
      "create-agent",
      () => createAutonomyAgent(payload),
      "Agent created",
      `Created autonomy agent ${trimmedName}.`
    );

    setAgentForm((currentValue) => ({
      ...currentValue,
      name: "",
      description: "",
    }));
  }

  async function handleCreateSchedule(event) {
    event.preventDefault();
    setFormErrors((currentValue) => ({ ...currentValue, schedule: "" }));

    if (!scheduleForm.agentId) {
      setFormErrors((currentValue) => ({
        ...currentValue,
        schedule: "Select an agent before creating a schedule.",
      }));
      return;
    }

    let payloadBody;
    try {
      payloadBody = parseJsonInput(scheduleForm.payload, "Schedule payload");
    } catch (error) {
      setFormErrors((currentValue) => ({
        ...currentValue,
        schedule: toErrorMessage(error, "Schedule payload is invalid."),
      }));
      return;
    }

    const payload = {
      agent_id: scheduleForm.agentId,
      interval_seconds: Number(scheduleForm.intervalSeconds),
      goal_override: scheduleForm.goalOverride.trim() || null,
      payload: payloadBody,
      enabled: scheduleForm.enabled,
    };

    await performAction(
      "create-schedule",
      () => createAutonomySchedule(payload),
      "Schedule created",
      `Created a schedule for ${scheduleForm.agentId}.`
    );
  }

  async function handleCreateInboxItem(event) {
    event.preventDefault();
    setFormErrors((currentValue) => ({ ...currentValue, inbox: "" }));

    if (!inboxForm.agentId || !inboxForm.goal.trim()) {
      setFormErrors((currentValue) => ({
        ...currentValue,
        inbox: "Agent and goal are required.",
      }));
      return;
    }

    let payloadBody;
    try {
      payloadBody = parseJsonInput(inboxForm.payload, "Inbox payload");
    } catch (error) {
      setFormErrors((currentValue) => ({
        ...currentValue,
        inbox: toErrorMessage(error, "Inbox payload is invalid."),
      }));
      return;
    }

    await performAction(
      "create-inbox",
      () =>
        createAutonomyInboxItem({
          agent_id: inboxForm.agentId,
          goal: inboxForm.goal.trim(),
          payload: payloadBody,
        }),
      "Inbox item queued",
      `Queued inbox work for ${inboxForm.agentId}.`
    );

    setInboxForm((currentValue) => ({ ...currentValue, goal: "" }));
  }

  function handleAgentFormChange(field, value) {
    setAgentForm((currentValue) => ({ ...currentValue, [field]: value }));
  }

  function handleScheduleFormChange(field, value) {
    setScheduleForm((currentValue) => ({ ...currentValue, [field]: value }));
  }

  function handleInboxFormChange(field, value) {
    setInboxForm((currentValue) => ({ ...currentValue, [field]: value }));
  }

  function handlePauseAgent(agent) {
    return performAction(
      `pause:${agent.agent_id}`,
      () => pauseAutonomyAgent(agent.agent_id),
      "Agent paused",
      `Paused ${agent.name}.`
    );
  }

  function handleResumeAgent(agent) {
    return performAction(
      `resume:${agent.agent_id}`,
      () => resumeAutonomyAgent(agent.agent_id),
      "Agent resumed",
      `Resumed ${agent.name}.`
    );
  }

  function handleStopAgent(agent) {
    return performAction(
      `stop:${agent.agent_id}`,
      () => stopAutonomyAgent(agent.agent_id),
      "Agent stopped",
      `Stopped ${agent.name}.`
    );
  }

  function handleEnableSchedule(schedule) {
    return performAction(
      `enable-schedule:${schedule.schedule_id}`,
      () => enableAutonomySchedule(schedule.schedule_id),
      "Schedule enabled",
      `Enabled ${schedule.schedule_id}.`
    );
  }

  function handleDisableSchedule(schedule) {
    return performAction(
      `disable-schedule:${schedule.schedule_id}`,
      () => disableAutonomySchedule(schedule.schedule_id),
      "Schedule disabled",
      `Disabled ${schedule.schedule_id}.`
    );
  }

  function handleCancelInboxItem(item) {
    return performAction(
      `cancel-inbox:${item.item_id}`,
      () => cancelAutonomyInboxItem(item.item_id),
      "Inbox item cancelled",
      `Cancelled ${item.item_id}.`
    );
  }

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
  const selectedRunSummary = selectedRunId ? runSummaries[selectedRunId] : null;
  const degradedResourceKeys = Object.entries(resourceErrors)
    .filter(([, message]) => Boolean(message))
    .map(([resourceKey]) => resourceKey);
  const isStaleData = Boolean(lastAttemptedSyncAt && lastSuccessfulSyncAt) &&
    new Date(lastAttemptedSyncAt).getTime() - new Date(lastSuccessfulSyncAt).getTime() >= STALE_SYNC_THRESHOLD_MS;

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
    refreshWorkspace: () => requestWorkspaceLoadRef.current?.(false),
    refreshing,
    resourceErrors,
    runSummaries,
    scheduleForm,
    schedules,
    selectedRunSummary,
    setKillReason,
    supervisorTone,
  };
}
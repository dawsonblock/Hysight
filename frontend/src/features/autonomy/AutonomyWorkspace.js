import { useEffect, useState } from "react";
import "@/features/autonomy/AutonomyWorkspace.css";
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
  getRunSummary,
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
  toErrorMessage,
} from "@/lib/api";
import { toast } from "@/hooks/use-toast";

const POLL_INTERVAL_MS = 15000;

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

function formatLabel(value, fallback = "Unavailable") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  return String(value)
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatBooleanLabel(value) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  return value ? "Yes" : "No";
}

function formatTimestamp(value, fallback = "Unavailable") {
  if (!value) {
    return fallback;
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }

  return parsed.toLocaleString();
}

function formatNumber(value, fallback = "Unavailable") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  return String(value);
}

function summarizeReanchor(summary) {
  if (!summary) {
    return "No recent re-anchor summary.";
  }

  if (typeof summary === "string") {
    return summary;
  }

  if (typeof summary === "object") {
    if (typeof summary.summary === "string" && summary.summary.trim()) {
      return summary.summary.trim();
    }

    const fragments = Object.entries(summary)
      .filter(([, entryValue]) => entryValue !== null && entryValue !== undefined && entryValue !== "")
      .slice(0, 3)
      .map(([key, entryValue]) => `${formatLabel(key)}: ${String(entryValue)}`);

    if (fragments.length > 0) {
      return fragments.join(" • ");
    }
  }

  return "Re-anchor summary available.";
}

function payloadPreview(payload) {
  if (!payload || typeof payload !== "object" || Object.keys(payload).length === 0) {
    return "No payload";
  }

  const serialized = JSON.stringify(payload);
  return serialized.length > 120
    ? `${serialized.slice(0, 117)}...`
    : serialized;
}

function parseJsonInput(text, label) {
  const trimmed = text.trim();
  if (!trimmed) {
    return {};
  }

  try {
    const payload = JSON.parse(trimmed);
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new Error(`${label} must be a JSON object.`);
    }
    return payload;
  } catch (error) {
    if (error instanceof Error && error.message.includes("must be a JSON object")) {
      throw error;
    }
    throw new Error(`${label} must be valid JSON.`);
  }
}

function latestBy(items, getKey, getTimestamp) {
  return items.reduce((accumulator, item) => {
    const key = getKey(item);
    if (!key) {
      return accumulator;
    }

    const currentTimestamp = new Date(getTimestamp(item) || 0).getTime();
    const previousItem = accumulator[key];
    const previousTimestamp = previousItem
      ? new Date(getTimestamp(previousItem) || 0).getTime()
      : -1;

    if (!previousItem || currentTimestamp >= previousTimestamp) {
      accumulator[key] = item;
    }

    return accumulator;
  }, {});
}

function buildCountMap(items, getKey) {
  return items.reduce((accumulator, item) => {
    const key = getKey(item);
    if (!key) {
      return accumulator;
    }
    accumulator[key] = (accumulator[key] || 0) + 1;
    return accumulator;
  }, {});
}

function PanelMessage({ text, tone = "default" }) {
  return <div className={`autonomy-panelMessage autonomy-panelMessage--${tone}`}>{text}</div>;
}

function StatusPill({ value, tone = "neutral" }) {
  return <span className={`autonomy-status autonomy-status--${tone}`}>{value}</span>;
}

function SectionHeader({ title, description, count, actions }) {
  return (
    <div className="autonomy-sectionHeader">
      <div>
        <div className="autonomy-sectionTitleRow">
          <h3 className="autonomy-sectionTitle">{title}</h3>
          {count !== undefined ? <span className="autonomy-sectionCount">{count}</span> : null}
        </div>
        {description ? <p className="autonomy-sectionDescription">{description}</p> : null}
      </div>
      {actions ? <div className="autonomy-sectionActions">{actions}</div> : null}
    </div>
  );
}

function MetricCard({ label, value, hint, tone = "neutral" }) {
  return (
    <article className={`autonomy-metric autonomy-metric--${tone}`}>
      <div className="autonomy-metricLabel">{label}</div>
      <div className="autonomy-metricValue">{value}</div>
      {hint ? <div className="autonomy-metricHint">{hint}</div> : null}
    </article>
  );
}

function ActionButton({ children, busy, tone = "default", ...props }) {
  return (
    <button
      {...props}
      className={`autonomy-button autonomy-button--${tone}${props.className ? ` ${props.className}` : ""}`}
      disabled={busy || props.disabled}
      type={props.type || "button"}
    >
      {busy ? "Working…" : children}
    </button>
  );
}

function TableCell({ children, ...props }) {
  return <td className="autonomy-tableCell" {...props}>{children}</td>;
}

function TableHeader({ children, ...props }) {
  return <th className="autonomy-tableHeader" {...props}>{children}</th>;
}

export default function AutonomyWorkspace({ onOpenRun, selectedRunId }) {
  const [resourceData, setResourceData] = useState(EMPTY_DATA);
  const [resourceErrors, setResourceErrors] = useState(EMPTY_ERRORS);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);
  const [actionKey, setActionKey] = useState("");
  const [actionNotice, setActionNotice] = useState(null);
  const [killReason, setKillReason] = useState("");
  const [formErrors, setFormErrors] = useState({ agent: "", schedule: "", inbox: "" });
  const [agentForm, setAgentForm] = useState({
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
  });
  const [scheduleForm, setScheduleForm] = useState({
    agentId: "",
    intervalSeconds: "300",
    goalOverride: "",
    payload: "{}",
    enabled: true,
  });
  const [inboxForm, setInboxForm] = useState({
    agentId: "",
    goal: "",
    payload: "{}",
  });

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

  useEffect(() => {
    let cancelled = false;

    async function loadWorkspace(isPolling = false) {
      if (!hasLoadedOnce && !isPolling) {
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
        loaderEntries.map(([, loader]) => loader())
      );

      if (cancelled) {
        return;
      }

      const nextErrors = { ...EMPTY_ERRORS };
      const nextValues = {};

      loaderEntries.forEach(([resourceKey], index) => {
        const result = settledResources[index];

        if (result.status === "fulfilled") {
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

      const currentRuns = nextValues.runs || [];
      const runIds = Array.from(
        new Set(currentRuns.map((runRecord) => runRecord.run_id).filter(Boolean))
      );

      const nextRunSummaries = {};
      if (runIds.length > 0) {
        const settledSummaries = await Promise.allSettled(
          runIds.map((runId) => getRunSummary(runId))
        );

        if (cancelled) {
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

      setResourceData((currentValue) => ({
        ...currentValue,
        ...nextValues,
        runSummaries:
          Object.keys(nextRunSummaries).length > 0
            ? nextRunSummaries
            : currentValue.runSummaries,
      }));
      setResourceErrors(nextErrors);
      setHasLoadedOnce(true);
      setLoading(false);
      setRefreshing(false);
      setLastUpdatedAt(new Date().toISOString());
    }

    loadWorkspace(false);
    const intervalId = window.setInterval(() => {
      loadWorkspace(true);
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [hasLoadedOnce, refreshNonce]);

  async function performAction(key, operation, successTitle, successDescription) {
    setActionKey(key);
    setActionNotice(null);

    try {
      await operation();
      setActionNotice({ tone: "success", text: successDescription });
      toast({ title: successTitle, description: successDescription });
      setRefreshNonce((currentValue) => currentValue + 1);
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
            {refreshing ? "Refreshing…" : `Last updated ${formatTimestamp(lastUpdatedAt, "Not loaded yet")}`}
          </div>
          <ActionButton
            busy={actionKey === "refresh"}
            onClick={() => setRefreshNonce((currentValue) => currentValue + 1)}
            tone="secondary"
          >
            Refresh now
          </ActionButton>
        </div>
      </div>

      {actionNotice ? <PanelMessage text={actionNotice.text} tone={actionNotice.tone} /> : null}
      {resourceErrors.status ? <PanelMessage text={resourceErrors.status} tone="error" /> : null}

      <section className="autonomy-panel">
        <SectionHeader
          title="Supervisor status"
          description="Compact operator summary of the backend autonomy supervisor."
        />
        {loading && !autonomyStatus ? (
          <PanelMessage text="Loading autonomy supervisor state…" />
        ) : autonomyStatus ? (
          <div className="autonomy-metricGrid">
            <MetricCard
              label="Supervisor"
              value={autonomyStatus.running ? "Running" : "Stopped"}
              hint={`Enabled: ${formatBooleanLabel(autonomyStatus.enabled)} • Loop: ${formatBooleanLabel(autonomyStatus.loop_running)}`}
              tone={supervisorTone}
            />
            <MetricCard
              label="Kill switch"
              value={autonomyStatus.kill_switch_active ? "Active" : "Clear"}
              hint={autonomyStatus.kill_switch_reason || "No active kill-switch reason."}
              tone={autonomyStatus.kill_switch_active ? "danger" : "success"}
            />
            <MetricCard
              label="Active agents"
              value={formatNumber(autonomyStatus.active_agents, "0")}
              hint={`Pending triggers: ${formatNumber(autonomyStatus.pending_triggers, "0")}`}
              tone="neutral"
            />
            <MetricCard
              label="Active autonomous runs"
              value={formatNumber(autonomyStatus.active_runs, "0")}
              hint={`Pending escalations: ${formatNumber(autonomyStatus.pending_escalations, "0")}`}
              tone={(autonomyStatus.pending_escalations || 0) > 0 ? "warning" : "neutral"}
            />
            <MetricCard
              label="Last decision"
              value={formatLabel(autonomyStatus.last_evaluator_decision)}
              hint={`Checkpoint: ${formatLabel(autonomyStatus.last_checkpoint?.status)}`}
              tone="neutral"
            />
            <MetricCard
              label="Last tick"
              value={formatTimestamp(autonomyStatus.last_tick_at)}
              hint={`Dedupe keys: ${formatNumber(autonomyStatus.dedupe_keys_tracked, "0")}`}
              tone="neutral"
            />
            <MetricCard
              label="Attention mode"
              value={formatLabel(autonomyStatus.current_attention_mode)}
              hint={`Interrupt queue: ${formatNumber(autonomyStatus.interrupt_queue_length, "0")}`}
              tone={autonomyStatus.reanchor_due ? "warning" : "neutral"}
            />
            <MetricCard
              label="Novelty budget"
              value={formatNumber(autonomyStatus.novelty_budget_remaining)}
              hint={`Hyperfocus steps used: ${formatNumber(autonomyStatus.hyperfocus_steps_used, "0")}`}
              tone="neutral"
            />
            <MetricCard
              label="Latest re-anchor"
              value={summarizeReanchor(autonomyStatus.last_reanchor_summary)}
              hint={`Last checkpointed: ${formatTimestamp(autonomyStatus.last_checkpoint?.checkpointed_at)}`}
              tone={autonomyStatus.reanchor_due ? "warning" : "neutral"}
            />
            <MetricCard
              label="Budget ledgers"
              value={formatNumber(budgets.length, "0")}
              hint={
                budgets[0]
                  ? `Observed steps: ${formatNumber(budgets[0].total_steps_observed, "0")} • Retries: ${formatNumber(budgets[0].total_retries_used, "0")}`
                  : "No budget ledgers returned."
              }
              tone="neutral"
            />
          </div>
        ) : (
          <PanelMessage text="No autonomy status returned by the backend." tone="error" />
        )}
      </section>

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
                onChange={(event) => setKillReason(event.target.value)}
                placeholder="Operator reason recorded with kill-switch activation"
                value={killReason}
              />
            </label>
            <div className="autonomy-inlineActions">
              <ActionButton
                busy={actionKey === "kill"}
                disabled={autonomyStatus?.kill_switch_active}
                onClick={() => handleKillSwitchChange(true)}
                tone="danger"
              >
                Kill autonomy
              </ActionButton>
              <ActionButton
                busy={actionKey === "unkill"}
                disabled={!autonomyStatus?.kill_switch_active}
                onClick={() => handleKillSwitchChange(false)}
                tone="success"
              >
                Clear kill switch
              </ActionButton>
            </div>
          </div>
        </div>
      </section>

      <div className="autonomy-grid autonomy-grid--twoColumn">
        <section className="autonomy-panel">
          <SectionHeader
            title="Agents"
            count={agents.length}
            description="Pause, resume, stop, and inspect bounded operator agents."
          />
          {resourceErrors.agents ? <PanelMessage text={resourceErrors.agents} tone="error" /> : null}
          <div className="autonomy-tableWrap">
            <table className="autonomy-table">
              <thead>
                <tr>
                  <TableHeader>Agent</TableHeader>
                  <TableHeader>Status</TableHeader>
                  <TableHeader>Style profile</TableHeader>
                  <TableHeader>Attention mode</TableHeader>
                  <TableHeader>Novelty budget</TableHeader>
                  <TableHeader>Re-anchor due</TableHeader>
                  <TableHeader>Interrupt queue</TableHeader>
                  <TableHeader>Active runs</TableHeader>
                  <TableHeader>Escalations</TableHeader>
                  <TableHeader>Last re-anchor</TableHeader>
                  <TableHeader>Actions</TableHeader>
                </tr>
              </thead>
              <tbody>
                {agents.length === 0 ? (
                  <tr>
                    <TableCell colSpan={11}>No autonomy agents returned.</TableCell>
                  </tr>
                ) : (
                  agents.map((agent) => {
                    const latestCheckpoint = latestCheckpointByAgent[agent.agent_id];
                    const budgetLedger = budgetByAgent[agent.agent_id];
                    const pendingEscalations = escalationCountByAgent[agent.agent_id] || 0;
                    const activeRunCount = activeRunCountByAgent[agent.agent_id] || 0;
                    return (
                      <tr key={agent.agent_id}>
                        <TableCell>
                          <div className="autonomy-strongCell">{agent.name}</div>
                          <div className="autonomy-subtleCell">{agent.agent_id}</div>
                        </TableCell>
                        <TableCell>
                          <StatusPill
                            tone={
                              agent.status === "active"
                                ? "success"
                                : agent.status === "paused"
                                  ? "warning"
                                  : "danger"
                            }
                            value={formatLabel(agent.status)}
                          />
                        </TableCell>
                        <TableCell>{agent.style_profile_id}</TableCell>
                        <TableCell>{formatLabel(latestCheckpoint?.current_attention_mode)}</TableCell>
                        <TableCell>
                          {formatNumber(
                            latestCheckpoint?.novelty_budget_remaining,
                            formatNumber(autonomyStatus?.novelty_budget_remaining)
                          )}
                        </TableCell>
                        <TableCell>{formatBooleanLabel(latestCheckpoint?.reanchor_due)}</TableCell>
                        <TableCell>{formatNumber(latestCheckpoint?.interrupt_queue_length, "0")}</TableCell>
                        <TableCell>{formatNumber(activeRunCount, "0")}</TableCell>
                        <TableCell>{formatNumber(pendingEscalations, "0")}</TableCell>
                        <TableCell>{summarizeReanchor(latestCheckpoint?.last_reanchor_summary)}</TableCell>
                        <TableCell>
                          <div className="autonomy-inlineActions autonomy-inlineActions--table">
                            <ActionButton
                              busy={actionKey === `pause:${agent.agent_id}`}
                              disabled={agent.status === "paused"}
                              onClick={() =>
                                performAction(
                                  `pause:${agent.agent_id}`,
                                  () => pauseAutonomyAgent(agent.agent_id),
                                  "Agent paused",
                                  `Paused ${agent.name}.`
                                )
                              }
                            >
                              Pause
                            </ActionButton>
                            <ActionButton
                              busy={actionKey === `resume:${agent.agent_id}`}
                              disabled={agent.status === "active"}
                              onClick={() =>
                                performAction(
                                  `resume:${agent.agent_id}`,
                                  () => resumeAutonomyAgent(agent.agent_id),
                                  "Agent resumed",
                                  `Resumed ${agent.name}.`
                                )
                              }
                              tone="success"
                            >
                              Resume
                            </ActionButton>
                            <ActionButton
                              busy={actionKey === `stop:${agent.agent_id}`}
                              disabled={agent.status === "stopped"}
                              onClick={() =>
                                performAction(
                                  `stop:${agent.agent_id}`,
                                  () => stopAutonomyAgent(agent.agent_id),
                                  "Agent stopped",
                                  `Stopped ${agent.name}.`
                                )
                              }
                              tone="danger"
                            >
                              Stop
                            </ActionButton>
                          </div>
                          {budgetLedger ? (
                            <div className="autonomy-subtleCell">
                              Steps {formatNumber(budgetLedger.total_steps_observed, "0")} • Retries {formatNumber(budgetLedger.total_retries_used, "0")}
                            </div>
                          ) : null}
                        </TableCell>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <form className="autonomy-form" onSubmit={handleCreateAgent}>
            <div className="autonomy-formTitle">Create agent</div>
            <div className="autonomy-formGrid autonomy-formGrid--three">
              <label className="autonomy-field">
                <span className="autonomy-fieldLabel">Name</span>
                <input
                  className="autonomy-input"
                  onChange={(event) => setAgentForm((currentValue) => ({ ...currentValue, name: event.target.value }))}
                  value={agentForm.name}
                />
              </label>
              <label className="autonomy-field">
                <span className="autonomy-fieldLabel">Description</span>
                <input
                  className="autonomy-input"
                  onChange={(event) => setAgentForm((currentValue) => ({ ...currentValue, description: event.target.value }))}
                  value={agentForm.description}
                />
              </label>
              <label className="autonomy-field">
                <span className="autonomy-fieldLabel">Style profile id</span>
                <input
                  className="autonomy-input"
                  onChange={(event) => setAgentForm((currentValue) => ({ ...currentValue, styleProfileId: event.target.value }))}
                  value={agentForm.styleProfileId}
                />
              </label>
              <label className="autonomy-field">
                <span className="autonomy-fieldLabel">Max steps / run</span>
                <input
                  className="autonomy-input"
                  min="1"
                  onChange={(event) => setAgentForm((currentValue) => ({ ...currentValue, maxStepsPerRun: event.target.value }))}
                  type="number"
                  value={agentForm.maxStepsPerRun}
                />
              </label>
              <label className="autonomy-field">
                <span className="autonomy-fieldLabel">Max runs / agent</span>
                <input
                  className="autonomy-input"
                  min="1"
                  onChange={(event) => setAgentForm((currentValue) => ({ ...currentValue, maxRunsPerAgent: event.target.value }))}
                  type="number"
                  value={agentForm.maxRunsPerAgent}
                />
              </label>
              <label className="autonomy-field">
                <span className="autonomy-fieldLabel">Max parallel runs</span>
                <input
                  className="autonomy-input"
                  min="1"
                  onChange={(event) => setAgentForm((currentValue) => ({ ...currentValue, maxParallelRuns: event.target.value }))}
                  type="number"
                  value={agentForm.maxParallelRuns}
                />
              </label>
              <label className="autonomy-field">
                <span className="autonomy-fieldLabel">Max retries / step</span>
                <input
                  className="autonomy-input"
                  min="0"
                  onChange={(event) => setAgentForm((currentValue) => ({ ...currentValue, maxRetriesPerStep: event.target.value }))}
                  type="number"
                  value={agentForm.maxRetriesPerStep}
                />
              </label>
              <label className="autonomy-field">
                <span className="autonomy-fieldLabel">Max run duration (s)</span>
                <input
                  className="autonomy-input"
                  min="1"
                  onChange={(event) => setAgentForm((currentValue) => ({ ...currentValue, maxRunDurationSeconds: event.target.value }))}
                  type="number"
                  value={agentForm.maxRunDurationSeconds}
                />
              </label>
              <label className="autonomy-field">
                <span className="autonomy-fieldLabel">Deadman timeout (s)</span>
                <input
                  className="autonomy-input"
                  min="1"
                  onChange={(event) => setAgentForm((currentValue) => ({ ...currentValue, deadmanTimeoutSeconds: event.target.value }))}
                  type="number"
                  value={agentForm.deadmanTimeoutSeconds}
                />
              </label>
            </div>

            <div className="autonomy-toggleRow">
              <label className="autonomy-checkbox">
                <input
                  checked={agentForm.enabled}
                  onChange={(event) => setAgentForm((currentValue) => ({ ...currentValue, enabled: event.target.checked }))}
                  type="checkbox"
                />
                Policy enabled
              </label>
              <label className="autonomy-checkbox">
                <input
                  checked={agentForm.allowMemoryWrites}
                  onChange={(event) => setAgentForm((currentValue) => ({ ...currentValue, allowMemoryWrites: event.target.checked }))}
                  type="checkbox"
                />
                Allow memory writes
              </label>
              <label className="autonomy-checkbox">
                <input
                  checked={agentForm.allowExternalWrites}
                  onChange={(event) => setAgentForm((currentValue) => ({ ...currentValue, allowExternalWrites: event.target.checked }))}
                  type="checkbox"
                />
                Allow external writes
              </label>
              <label className="autonomy-checkbox">
                <input
                  checked={agentForm.autoResumeAfterApproval}
                  onChange={(event) => setAgentForm((currentValue) => ({ ...currentValue, autoResumeAfterApproval: event.target.checked }))}
                  type="checkbox"
                />
                Auto-resume after approval
              </label>
            </div>

            {formErrors.agent ? <PanelMessage text={formErrors.agent} tone="error" /> : null}
            <div className="autonomy-formActions">
              <ActionButton busy={actionKey === "create-agent"} type="submit" tone="success">
                Create agent
              </ActionButton>
            </div>
          </form>
        </section>

        <section className="autonomy-panel">
          <SectionHeader
            title="Schedules"
            count={schedules.length}
            description="Enable and disable backend schedule bindings without leaving the operator shell."
          />
          {resourceErrors.schedules ? <PanelMessage text={resourceErrors.schedules} tone="error" /> : null}
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
                  <tr>
                    <TableCell colSpan={7}>No schedules returned.</TableCell>
                  </tr>
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
                        <StatusPill
                          tone={schedule.enabled ? "success" : "danger"}
                          value={schedule.enabled ? "Enabled" : "Disabled"}
                        />
                      </TableCell>
                      <TableCell>{formatTimestamp(schedule.last_fired_at)}</TableCell>
                      <TableCell>
                        <div className="autonomy-inlineActions autonomy-inlineActions--table">
                          <ActionButton
                            busy={actionKey === `enable-schedule:${schedule.schedule_id}`}
                            disabled={schedule.enabled}
                            onClick={() =>
                              performAction(
                                `enable-schedule:${schedule.schedule_id}`,
                                () => enableAutonomySchedule(schedule.schedule_id),
                                "Schedule enabled",
                                `Enabled ${schedule.schedule_id}.`
                              )
                            }
                            tone="success"
                          >
                            Enable
                          </ActionButton>
                          <ActionButton
                            busy={actionKey === `disable-schedule:${schedule.schedule_id}`}
                            disabled={!schedule.enabled}
                            onClick={() =>
                              performAction(
                                `disable-schedule:${schedule.schedule_id}`,
                                () => disableAutonomySchedule(schedule.schedule_id),
                                "Schedule disabled",
                                `Disabled ${schedule.schedule_id}.`
                              )
                            }
                            tone="danger"
                          >
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

          <form className="autonomy-form" onSubmit={handleCreateSchedule}>
            <div className="autonomy-formTitle">Create schedule</div>
            <div className="autonomy-formGrid autonomy-formGrid--three">
              <label className="autonomy-field">
                <span className="autonomy-fieldLabel">Agent</span>
                <select
                  className="autonomy-select"
                  onChange={(event) => setScheduleForm((currentValue) => ({ ...currentValue, agentId: event.target.value }))}
                  value={scheduleForm.agentId}
                >
                  <option value="">Select agent</option>
                  {agents.map((agent) => (
                    <option
                      key={agent.agent_id}
                      label={`${agent.name} (${agent.agent_id})`}
                      value={agent.agent_id}
                    />
                  ))}
                </select>
              </label>
              <label className="autonomy-field">
                <span className="autonomy-fieldLabel">Interval seconds</span>
                <input
                  className="autonomy-input"
                  min="1"
                  onChange={(event) => setScheduleForm((currentValue) => ({ ...currentValue, intervalSeconds: event.target.value }))}
                  type="number"
                  value={scheduleForm.intervalSeconds}
                />
              </label>
              <label className="autonomy-field">
                <span className="autonomy-fieldLabel">Goal override</span>
                <input
                  className="autonomy-input"
                  onChange={(event) => setScheduleForm((currentValue) => ({ ...currentValue, goalOverride: event.target.value }))}
                  value={scheduleForm.goalOverride}
                />
              </label>
              <label className="autonomy-field autonomy-field--wide">
                <span className="autonomy-fieldLabel">Payload JSON</span>
                <textarea
                  className="autonomy-textarea"
                  onChange={(event) => setScheduleForm((currentValue) => ({ ...currentValue, payload: event.target.value }))}
                  rows={4}
                  value={scheduleForm.payload}
                />
              </label>
            </div>

            <label className="autonomy-checkbox">
              <input
                checked={scheduleForm.enabled}
                onChange={(event) => setScheduleForm((currentValue) => ({ ...currentValue, enabled: event.target.checked }))}
                type="checkbox"
              />
              Enabled on create
            </label>

            {formErrors.schedule ? <PanelMessage text={formErrors.schedule} tone="error" /> : null}
            <div className="autonomy-formActions">
              <ActionButton busy={actionKey === "create-schedule"} type="submit" tone="success">
                Create schedule
              </ActionButton>
            </div>
          </form>
        </section>
      </div>

      <div className="autonomy-grid autonomy-grid--twoColumn">
        <section className="autonomy-panel">
          <SectionHeader
            title="Inbox"
            count={inboxItems.length}
            description="Queue or cancel backend inbox work for bounded agents."
          />
          {resourceErrors.inbox ? <PanelMessage text={resourceErrors.inbox} tone="error" /> : null}
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
                  <tr>
                    <TableCell colSpan={7}>No inbox items returned.</TableCell>
                  </tr>
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
                        <ActionButton
                          busy={actionKey === `cancel-inbox:${item.item_id}`}
                          disabled={item.status === "cancelled"}
                          onClick={() =>
                            performAction(
                              `cancel-inbox:${item.item_id}`,
                              () => cancelAutonomyInboxItem(item.item_id),
                              "Inbox item cancelled",
                              `Cancelled ${item.item_id}.`
                            )
                          }
                          tone="danger"
                        >
                          Cancel
                        </ActionButton>
                      </TableCell>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <form className="autonomy-form" onSubmit={handleCreateInboxItem}>
            <div className="autonomy-formTitle">Enqueue inbox item</div>
            <div className="autonomy-formGrid autonomy-formGrid--three">
              <label className="autonomy-field">
                <span className="autonomy-fieldLabel">Agent</span>
                <select
                  className="autonomy-select"
                  onChange={(event) => setInboxForm((currentValue) => ({ ...currentValue, agentId: event.target.value }))}
                  value={inboxForm.agentId}
                >
                  <option value="">Select agent</option>
                  {agents.map((agent) => (
                    <option
                      key={agent.agent_id}
                      label={`${agent.name} (${agent.agent_id})`}
                      value={agent.agent_id}
                    />
                  ))}
                </select>
              </label>
              <label className="autonomy-field autonomy-field--wide">
                <span className="autonomy-fieldLabel">Goal</span>
                <input
                  className="autonomy-input"
                  onChange={(event) => setInboxForm((currentValue) => ({ ...currentValue, goal: event.target.value }))}
                  value={inboxForm.goal}
                />
              </label>
              <label className="autonomy-field autonomy-field--wide">
                <span className="autonomy-fieldLabel">Payload JSON</span>
                <textarea
                  className="autonomy-textarea"
                  onChange={(event) => setInboxForm((currentValue) => ({ ...currentValue, payload: event.target.value }))}
                  rows={4}
                  value={inboxForm.payload}
                />
              </label>
            </div>
            {formErrors.inbox ? <PanelMessage text={formErrors.inbox} tone="error" /> : null}
            <div className="autonomy-formActions">
              <ActionButton busy={actionKey === "create-inbox"} type="submit" tone="success">
                Queue inbox work
              </ActionButton>
            </div>
          </form>
        </section>

        <section className="autonomy-panel">
          <SectionHeader
            title="Active autonomous runs"
            count={autonomyRuns.length}
            description="Inspect live autonomy run links and jump back into the existing replay surface."
          />
          {resourceErrors.runs ? <PanelMessage text={resourceErrors.runs} tone="error" /> : null}
          {resourceErrors.runSummaries ? <PanelMessage text={resourceErrors.runSummaries} tone="error" /> : null}
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
                  <tr>
                    <TableCell colSpan={9}>No active autonomous runs returned.</TableCell>
                  </tr>
                ) : (
                  autonomyRuns.map((runRecord) => {
                    const checkpoint = latestCheckpointByRun[runRecord.run_id];
                    const summary = runSummaries[runRecord.run_id];
                    const runEscalation = escalations.find((item) => item.run_id === runRecord.run_id);
                    const isSelectedRun = selectedRunId === runRecord.run_id;
                    return (
                      <tr key={`${runRecord.agent_id}:${runRecord.trigger_id}:${runRecord.run_id}`}>
                        <TableCell>
                          <div className="autonomy-strongCell">{runRecord.run_id}</div>
                          <div className="autonomy-subtleCell">{summary?.goal || "Goal unavailable"}</div>
                        </TableCell>
                        <TableCell>{runRecord.agent_id}</TableCell>
                        <TableCell>{runRecord.trigger_id}</TableCell>
                        <TableCell>{formatLabel(summary?.state)}</TableCell>
                        <TableCell>{formatLabel(checkpoint?.current_attention_mode)}</TableCell>
                        <TableCell>{formatLabel(checkpoint?.last_decision || autonomyStatus?.last_evaluator_decision)}</TableCell>
                        <TableCell>{formatLabel(checkpoint?.status)}</TableCell>
                        <TableCell>
                          <StatusPill
                            tone={
                              autonomyStatus?.kill_switch_active
                                ? "danger"
                                : runEscalation
                                  ? "warning"
                                  : "neutral"
                            }
                            value={
                              autonomyStatus?.kill_switch_active
                                ? "Kill switch active"
                                : runEscalation
                                  ? "Escalated"
                                  : "Clear"
                            }
                          />
                        </TableCell>
                        <TableCell>
                          <ActionButton
                            onClick={() => onOpenRun(runRecord.run_id)}
                            tone={isSelectedRun ? "success" : "secondary"}
                          >
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
      </div>

      <div className="autonomy-grid autonomy-grid--threeColumn">
        <section className="autonomy-panel">
          <SectionHeader
            title="Escalations"
            count={escalations.length}
            description="Pending autonomy escalations linked back to ordinary run replay."
          />
          {resourceErrors.escalations ? <PanelMessage text={resourceErrors.escalations} tone="error" /> : null}
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
                  <tr>
                    <TableCell colSpan={6}>No escalations returned.</TableCell>
                  </tr>
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
                          <ActionButton onClick={() => onOpenRun(escalation.run_id)} tone="secondary">
                            Open replay
                          </ActionButton>
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

        <section className="autonomy-panel">
          <SectionHeader
            title="Budget ledgers"
            count={budgets.length}
            description="See which agents are approaching bounded runtime limits."
          />
          {resourceErrors.budgets ? <PanelMessage text={resourceErrors.budgets} tone="error" /> : null}
          <div className="autonomy-tableWrap">
            <table className="autonomy-table">
              <thead>
                <tr>
                  <TableHeader>Agent</TableHeader>
                  <TableHeader>Launched runs</TableHeader>
                  <TableHeader>Active runs</TableHeader>
                  <TableHeader>Steps observed</TableHeader>
                  <TableHeader>Retries used</TableHeader>
                  <TableHeader>Last breach</TableHeader>
                  <TableHeader>Deadman / timeout</TableHeader>
                </tr>
              </thead>
              <tbody>
                {budgets.length === 0 ? (
                  <tr>
                    <TableCell colSpan={7}>No budget ledgers returned.</TableCell>
                  </tr>
                ) : (
                  budgets.map((ledger) => (
                    <tr key={ledger.agent_id}>
                      <TableCell>{ledger.agent_id}</TableCell>
                      <TableCell>{formatNumber(ledger.launched_runs_total, "0")}</TableCell>
                      <TableCell>{formatNumber(ledger.active_runs, "0")}</TableCell>
                      <TableCell>{formatNumber(ledger.total_steps_observed, "0")}</TableCell>
                      <TableCell>{formatNumber(ledger.total_retries_used, "0")}</TableCell>
                      <TableCell>{formatTimestamp(ledger.last_budget_breach_at)}</TableCell>
                      <TableCell>{autonomyStatus?.kill_switch_active ? "Kill switch active" : "Unavailable"}</TableCell>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="autonomy-panel">
          <SectionHeader
            title="Style and attention"
            description="Operational style-layer state only. No human-like thoughts or medical framing."
          />
          <div className="autonomy-stylePanel">
            <div className="autonomy-styleSummary">
              <div>
                <div className="autonomy-keyValueLabel">Current attention mode</div>
                <div className="autonomy-keyValueValue">{formatLabel(autonomyStatus?.current_attention_mode)}</div>
              </div>
              <div>
                <div className="autonomy-keyValueLabel">Hyperfocus active</div>
                <div className="autonomy-keyValueValue">
                  {autonomyStatus?.hyperfocus_steps_used === null ||
                  autonomyStatus?.hyperfocus_steps_used === undefined
                    ? "Unavailable"
                    : autonomyStatus.hyperfocus_steps_used > 0
                      ? "Active"
                      : "Inactive"}
                </div>
              </div>
              <div>
                <div className="autonomy-keyValueLabel">Re-anchor due</div>
                <div className="autonomy-keyValueValue">{formatBooleanLabel(autonomyStatus?.reanchor_due)}</div>
              </div>
              <div>
                <div className="autonomy-keyValueLabel">Queued branches / interrupts</div>
                <div className="autonomy-keyValueValue">{formatNumber(autonomyStatus?.interrupt_queue_length, "0")}</div>
              </div>
              <div>
                <div className="autonomy-keyValueLabel">Latest re-anchor summary</div>
                <div className="autonomy-keyValueValue autonomy-keyValueValue--wrap">
                  {summarizeReanchor(autonomyStatus?.last_reanchor_summary)}
                </div>
              </div>
            </div>

            <div className="autonomy-tableWrap">
              <table className="autonomy-table">
                <thead>
                  <tr>
                    <TableHeader>Agent</TableHeader>
                    <TableHeader>Style profile</TableHeader>
                    <TableHeader>Attention</TableHeader>
                    <TableHeader>Hyperfocus steps</TableHeader>
                    <TableHeader>Novelty remaining</TableHeader>
                    <TableHeader>Re-anchor summary</TableHeader>
                  </tr>
                </thead>
                <tbody>
                  {agents.length === 0 ? (
                    <tr>
                      <TableCell colSpan={6}>No agents available for style inspection.</TableCell>
                    </tr>
                  ) : (
                    agents.map((agent) => {
                      const latestCheckpoint = latestCheckpointByAgent[agent.agent_id];
                      return (
                        <tr key={`style:${agent.agent_id}`}>
                          <TableCell>{agent.name}</TableCell>
                          <TableCell>{latestCheckpoint?.style_profile_id || agent.style_profile_id}</TableCell>
                          <TableCell>{formatLabel(latestCheckpoint?.current_attention_mode)}</TableCell>
                          <TableCell>{formatNumber(latestCheckpoint?.hyperfocus_steps_used, "0")}</TableCell>
                          <TableCell>{formatNumber(latestCheckpoint?.novelty_budget_remaining)}</TableCell>
                          <TableCell>{summarizeReanchor(latestCheckpoint?.last_reanchor_summary)}</TableCell>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>

      <section className="autonomy-panel">
        <SectionHeader
          title="Checkpoints"
          count={checkpoints.length}
          description="Inspection-only checkpoint history as exposed by the backend."
        />
        {resourceErrors.checkpoints ? <PanelMessage text={resourceErrors.checkpoints} tone="error" /> : null}
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
                <tr>
                  <TableCell colSpan={9}>No checkpoints returned.</TableCell>
                </tr>
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
                            <ActionButton onClick={() => onOpenRun(checkpoint.run_id)} tone="secondary">
                              Replay
                            </ActionButton>
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

      {selectedRunSummary ? (
        <section className="autonomy-panel autonomy-panel--selectedRun">
          <SectionHeader
            title="Selected run in replay"
            description="Autonomy navigation preserves the existing run-detail surface rather than duplicating replay in this workspace."
          />
          <div className="autonomy-selectedRunSummary">
            <div>
              <div className="autonomy-keyValueLabel">Run id</div>
              <div className="autonomy-keyValueValue">{selectedRunSummary.run_id}</div>
            </div>
            <div>
              <div className="autonomy-keyValueLabel">State</div>
              <div className="autonomy-keyValueValue">{formatLabel(selectedRunSummary.state)}</div>
            </div>
            <div>
              <div className="autonomy-keyValueLabel">Goal</div>
              <div className="autonomy-keyValueValue autonomy-keyValueValue--wrap">{selectedRunSummary.goal}</div>
            </div>
          </div>
        </section>
      ) : null}
    </section>
  );
}
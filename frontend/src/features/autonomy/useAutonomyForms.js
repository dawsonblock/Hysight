import { useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api";
import {
  createAutonomyAgent,
  createAutonomyInboxItem,
  createAutonomySchedule,
} from "@/lib/autonomy-api";
import { parseJsonInput } from "@/features/autonomy/formatters";

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

export default function useAutonomyForms({ agents, performAction }) {
  const [formErrors, setFormErrors] = useState({ agent: "", schedule: "", inbox: "" });
  const [agentForm, setAgentForm] = useState(INITIAL_AGENT_FORM);
  const [scheduleForm, setScheduleForm] = useState(INITIAL_SCHEDULE_FORM);
  const [inboxForm, setInboxForm] = useState(INITIAL_INBOX_FORM);

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

  return {
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
  };
}

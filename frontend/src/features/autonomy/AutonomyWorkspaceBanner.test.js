import { render, screen } from "@testing-library/react";
import AutonomyWorkspace from "@/features/autonomy/AutonomyWorkspace";
import useAutonomyWorkspaceController from "@/features/autonomy/useAutonomyWorkspaceController";

jest.mock("@/features/autonomy/useAutonomyWorkspaceController", () => jest.fn());

function buildControllerState(overrides = {}) {
  return {
    actionKey: "",
    actionNotice: null,
    activeRunCountByAgent: {},
    agentForm: {
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
    },
    agents: [],
    autonomyRuns: [],
    autonomyStatus: {
      enabled: true,
      running: true,
      active_agents: 0,
      active_runs: 0,
      pending_triggers: 0,
      pending_escalations: 0,
      loop_running: true,
      kill_switch_active: false,
      kill_switch_reason: null,
      kill_switch_set_at: null,
      last_tick_at: "2026-04-21T10:00:00Z",
      last_evaluator_decision: "continue",
      current_attention_mode: "review",
      interrupt_queue_length: 0,
      reanchor_due: false,
      novelty_budget_remaining: 4,
      hyperfocus_steps_used: 0,
      last_reanchor_summary: null,
      dedupe_keys_tracked: 0,
      last_checkpoint: null,
    },
    budgetByAgent: {},
    budgets: [],
    checkpoints: [],
    degradedResourceKeys: [],
    escalations: [],
    escalationCountByAgent: {},
    formErrors: { agent: "", schedule: "", inbox: "" },
    handleAgentFormChange: jest.fn(),
    handleCancelInboxItem: jest.fn(),
    handleCreateAgent: jest.fn(),
    handleCreateInboxItem: jest.fn(),
    handleCreateSchedule: jest.fn(),
    handleDisableSchedule: jest.fn(),
    handleEnableSchedule: jest.fn(),
    handleInboxFormChange: jest.fn(),
    handleKillSwitchChange: jest.fn(),
    handlePauseAgent: jest.fn(),
    handleResumeAgent: jest.fn(),
    handleScheduleFormChange: jest.fn(),
    handleStopAgent: jest.fn(),
    inboxForm: { agentId: "", goal: "", payload: "{}" },
    inboxItems: [],
    isStaleData: false,
    killReason: "",
    lastAttemptedSyncAt: "2026-04-21T10:05:00Z",
    lastSuccessfulSyncAt: "2026-04-21T10:00:00Z",
    latestCheckpointByAgent: {},
    latestCheckpointByRun: {},
    loading: false,
    refreshWorkspace: jest.fn(),
    refreshing: false,
    resourceErrors: {
      status: "",
      agents: "",
      schedules: "",
      inbox: "",
      runs: "",
      checkpoints: "",
      budgets: "",
      escalations: "",
      runSummaries: "",
    },
    runSummaries: {},
    scheduleForm: {
      agentId: "",
      intervalSeconds: "300",
      goalOverride: "",
      payload: "{}",
      enabled: true,
    },
    schedules: [],
    selectedRunSummary: null,
    setKillReason: jest.fn(),
    supervisorTone: "success",
    ...overrides,
  };
}

beforeEach(() => {
  useAutonomyWorkspaceController.mockReset();
});

test("shows a degraded backend banner when the controller reports panel failures", () => {
  useAutonomyWorkspaceController.mockReturnValue(
    buildControllerState({
      degradedResourceKeys: ["agents"],
      resourceErrors: {
        status: "",
        agents: "Agents offline",
        schedules: "",
        inbox: "",
        runs: "",
        checkpoints: "",
        budgets: "",
        escalations: "",
        runSummaries: "",
      },
    })
  );

  render(<AutonomyWorkspace onOpenRun={jest.fn()} selectedRunId={null} />);

  expect(screen.getByText(/Degraded backend state for agents/)).toBeInTheDocument();
  expect(screen.getByText("Agents offline")).toBeInTheDocument();
});

test("shows a stale-data banner when the controller reports stale autonomy state", () => {
  useAutonomyWorkspaceController.mockReturnValue(
    buildControllerState({
      isStaleData: true,
      lastSuccessfulSyncAt: "2026-04-21T09:45:00Z",
      lastAttemptedSyncAt: "2026-04-21T10:05:00Z",
    })
  );

  render(<AutonomyWorkspace onOpenRun={jest.fn()} selectedRunId={null} />);

  expect(screen.getByText(/Autonomy data is stale/)).toBeInTheDocument();
});
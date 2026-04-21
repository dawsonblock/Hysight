import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AutonomyWorkspace from "@/features/autonomy/AutonomyWorkspace";
import {
  cancelAutonomyInboxItem,
  clearAutonomyKillSwitch,
  createAutonomyAgent,
  createAutonomyInboxItem,
  createAutonomySchedule,
  disableAutonomySchedule,
  enableAutonomyKillSwitch,
  enableAutonomySchedule,
  getAutonomyWorkspace,
  pauseAutonomyAgent,
  resumeAutonomyAgent,
  stopAutonomyAgent,
} from "@/lib/autonomy-api";
import {
  getRunSummary,
} from "@/lib/api";

jest.mock("@/lib/autonomy-api", () => ({
  cancelAutonomyInboxItem: jest.fn(),
  clearAutonomyKillSwitch: jest.fn(),
  createAutonomyAgent: jest.fn(),
  createAutonomyInboxItem: jest.fn(),
  createAutonomySchedule: jest.fn(),
  disableAutonomySchedule: jest.fn(),
  enableAutonomyKillSwitch: jest.fn(),
  enableAutonomySchedule: jest.fn(),
  getAutonomyWorkspace: jest.fn(),
  pauseAutonomyAgent: jest.fn(),
  resumeAutonomyAgent: jest.fn(),
  stopAutonomyAgent: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  getRunSummary: jest.fn(),
  toErrorMessage: jest.fn((error, fallback) => error?.message || fallback),
}));

jest.mock("@/hooks/use-toast", () => ({
  toast: jest.fn(),
}));

const STATUS_FIXTURE = {
  enabled: true,
  running: true,
  active_agents: 2,
  active_runs: 1,
  pending_triggers: 3,
  pending_escalations: 1,
  loop_running: true,
  kill_switch_active: false,
  kill_switch_reason: null,
  kill_switch_set_at: null,
  last_tick_at: "2026-04-21T10:00:00Z",
  last_error: null,
  last_evaluator_decision: "escalate",
  current_attention_mode: "hyperfocus_review",
  interrupt_queue_length: 2,
  reanchor_due: true,
  novelty_budget_remaining: 4,
  hyperfocus_steps_used: 3,
  last_reanchor_summary: { summary: "Re-anchor preserved operator priority and narrowed focus." },
  dedupe_keys_tracked: 6,
  recent_runs: [
    { agent_id: "agent-1", trigger_id: "trigger-1", run_id: "run-autonomy-1" },
  ],
  budget_ledgers: [],
  last_checkpoint: {
    agent_id: "agent-1",
    trigger_id: "trigger-1",
    run_id: "run-autonomy-1",
    status: "awaiting_approval",
    attempt: 1,
    last_event_id: "event-1",
    last_state: "awaiting_approval",
    last_decision: "escalate",
    resume_allowed: false,
    safe_to_continue: false,
    kill_switch_observed: false,
    dedupe_key: "inbox:item-1",
    style_profile_id: "conservative_operator",
    current_attention_mode: "hyperfocus_review",
    current_subgoal: "Validate approval path",
    interrupt_queue_length: 2,
    reanchor_due: true,
    novelty_budget_remaining: 4,
    hyperfocus_steps_used: 3,
    last_reanchor_summary: { summary: "Re-anchor preserved operator priority and narrowed focus." },
    checkpointed_at: "2026-04-21T10:00:00Z",
    budget_snapshot: { style_novelty_budget: 8 },
  },
};

const AGENTS_FIXTURE = {
  agents: [
    {
      agent_id: "agent-1",
      name: "Release supervisor",
      description: "Monitors release-bound autonomy work.",
      mode: "bounded",
      status: "active",
      style_profile_id: "conservative_operator",
      policy: {
        mode: "bounded",
        enabled: true,
        budget: {
          max_steps_per_run: 50,
          max_runs_per_agent: 25,
          max_parallel_runs: 1,
          max_retries_per_step: 2,
          max_run_duration_seconds: 900,
          deadman_timeout_seconds: 1800,
        },
        allow_memory_writes: true,
        allow_external_writes: false,
        auto_resume_after_approval: false,
      },
      created_at: "2026-04-21T09:50:00Z",
      updated_at: "2026-04-21T10:00:00Z",
    },
  ],
};

const SCHEDULES_FIXTURE = {
  schedules: [
    {
      schedule_id: "schedule-1",
      agent_id: "agent-1",
      interval_seconds: 300,
      goal_override: "Check release proof drift",
      payload: { source: "operator" },
      enabled: true,
      last_fired_at: "2026-04-21T09:58:00Z",
      created_at: "2026-04-21T09:55:00Z",
      updated_at: "2026-04-21T09:58:00Z",
    },
  ],
};

const INBOX_FIXTURE = {
  items: [
    {
      item_id: "inbox-1",
      agent_id: "agent-1",
      goal: "Review release drift",
      payload: { priority: "operator" },
      status: "queued",
      created_at: "2026-04-21T09:59:00Z",
      claimed_at: null,
    },
  ],
};

const RUNS_FIXTURE = {
  runs: [
    { agent_id: "agent-1", trigger_id: "trigger-1", run_id: "run-autonomy-1", run_status: "awaiting_approval", last_state: "awaiting_approval", last_decision: "escalate" },
  ],
};

const CHECKPOINTS_FIXTURE = {
  checkpoints: [STATUS_FIXTURE.last_checkpoint],
};

const BUDGETS_FIXTURE = {
  ledgers: [
    {
      agent_id: "agent-1",
      launched_runs_total: 5,
      active_runs: 1,
      total_steps_observed: 11,
      total_retries_used: 1,
      last_run_started_at: "2026-04-21T09:58:30Z",
      last_run_completed_at: null,
      last_budget_breach_at: null,
      updated_at: "2026-04-21T10:00:00Z",
    },
  ],
};

const ESCALATIONS_FIXTURE = {
  escalations: [
    {
      agent_id: "agent-1",
      trigger_id: "trigger-1",
      run_id: "run-autonomy-1",
      status: "awaiting_approval",
      last_state: "awaiting_approval",
      last_decision: "escalate",
      checkpointed_at: "2026-04-21T10:00:00Z",
    },
  ],
};

const RUN_SUMMARY_FIXTURE = {
  run_id: "run-autonomy-1",
  goal: "Review release drift",
  state: "awaiting_approval",
};

function primeMocks(overrides = {}) {
  const statusData = overrides.status || STATUS_FIXTURE;
  const agentsData = overrides.agents || AGENTS_FIXTURE;
  const schedulesData = overrides.schedules || SCHEDULES_FIXTURE;
  const inboxData = overrides.inbox || INBOX_FIXTURE;
  const runsData = overrides.runs || RUNS_FIXTURE;
  const checkpointsData = overrides.checkpoints || CHECKPOINTS_FIXTURE;
  const budgetsData = overrides.budgets || BUDGETS_FIXTURE;
  const escalationsData = overrides.escalations || ESCALATIONS_FIXTURE;
  getAutonomyWorkspace.mockResolvedValue({
    snapshot_at: "2026-04-21T10:00:00Z",
    status: statusData,
    agents: agentsData.agents || agentsData || [],
    schedules: schedulesData.schedules || schedulesData || [],
    inbox: inboxData.items || inboxData || [],
    runs: runsData.runs || runsData || [],
    checkpoints: checkpointsData.checkpoints || checkpointsData || [],
    budgets: budgetsData.ledgers || budgetsData || [],
    escalations: escalationsData.escalations || escalationsData || [],
    section_errors: {},
  });
  getRunSummary.mockResolvedValue(overrides.runSummary || RUN_SUMMARY_FIXTURE);
  enableAutonomyKillSwitch.mockResolvedValue({ active: true, reason: "Operator hold" });
  clearAutonomyKillSwitch.mockResolvedValue({ active: false, reason: null });
  pauseAutonomyAgent.mockResolvedValue({ agent_id: "agent-1", status: "paused" });
  resumeAutonomyAgent.mockResolvedValue({ agent_id: "agent-1", status: "active" });
  stopAutonomyAgent.mockResolvedValue({ agent_id: "agent-1", status: "stopped" });
  enableAutonomySchedule.mockResolvedValue(SCHEDULES_FIXTURE.schedules[0]);
  disableAutonomySchedule.mockResolvedValue({
    ...SCHEDULES_FIXTURE.schedules[0],
    enabled: false,
  });
  cancelAutonomyInboxItem.mockResolvedValue({
    ...INBOX_FIXTURE.items[0],
    status: "cancelled",
  });
  createAutonomyAgent.mockResolvedValue(AGENTS_FIXTURE.agents[0]);
  createAutonomySchedule.mockResolvedValue(SCHEDULES_FIXTURE.schedules[0]);
  createAutonomyInboxItem.mockResolvedValue(INBOX_FIXTURE.items[0]);
}

function renderWorkspace(props = {}) {
  const onOpenRun = jest.fn();
  render(
    <AutonomyWorkspace
      onOpenRun={onOpenRun}
      selectedRunId={props.selectedRunId || null}
    />
  );
  return { onOpenRun };
}

beforeEach(() => {
  primeMocks();
});

afterEach(() => {
  jest.clearAllMocks();
});

test("renders backend autonomy status, style state, and replay links", async () => {
  const user = userEvent.setup();
  const { onOpenRun } = renderWorkspace({ selectedRunId: "run-autonomy-1" });

  expect(await screen.findByText("Supervisor status")).toBeInTheDocument();
  expect((await screen.findAllByText("Release supervisor")).length).toBeGreaterThan(0);
  expect((await screen.findAllByText("Hyperfocus Review")).length).toBeGreaterThan(0);
  expect(
    (await screen.findAllByText("Re-anchor preserved operator priority and narrowed focus.")).length
  ).toBeGreaterThan(0);
  expect((await screen.findAllByText("Review release drift")).length).toBeGreaterThan(0);

  await user.click(await screen.findByRole("button", { name: "Viewing in Runs" }));

  expect(onOpenRun).toHaveBeenCalledWith("run-autonomy-1");
});

test("shows confirmation for kill switch changes and calls the backend", async () => {
  const user = userEvent.setup();
  renderWorkspace();

  await screen.findByText("Kill switch");

  await user.click(screen.getByRole("button", { name: "Kill autonomy" }));

  await screen.findByText("Activate kill switch?");

  await user.type(
    screen.getByPlaceholderText(
      "Operator reason recorded with kill-switch activation"
    ),
    "Operator hold"
  );
  await user.click(screen.getByRole("button", { name: "Activate kill switch" }));

  await waitFor(() => {
    expect(enableAutonomyKillSwitch).toHaveBeenCalledWith({
      reason: "Operator hold",
    });
  });
});

test("calls agent control endpoints and degrades missing optional fields gracefully", async () => {
  const user = userEvent.setup();
  primeMocks({
    status: {
      ...STATUS_FIXTURE,
      current_attention_mode: null,
      novelty_budget_remaining: null,
      last_reanchor_summary: null,
    },
    checkpoints: {
      checkpoints: [
        {
          ...STATUS_FIXTURE.last_checkpoint,
          current_attention_mode: null,
          novelty_budget_remaining: null,
          last_reanchor_summary: null,
        },
      ],
    },
  });

  renderWorkspace();

  expect(await screen.findAllByText("Unavailable")).not.toHaveLength(0);
  expect(screen.getAllByText("No recent re-anchor summary.").length).toBeGreaterThan(0);

  expect((await screen.findAllByText("Release supervisor")).length).toBeGreaterThan(0);
  await user.click((await screen.findAllByRole("button", { name: "Pause" }))[0]);

  await waitFor(() => {
    expect(pauseAutonomyAgent).toHaveBeenCalledWith("agent-1");
  });
});
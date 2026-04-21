import { render, screen } from "@testing-library/react";
import AutonomyStatusHeader from "@/features/autonomy/components/AutonomyStatusHeader";

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
  reanchor_due: false,
  novelty_budget_remaining: 4,
  hyperfocus_steps_used: 3,
  last_reanchor_summary: { summary: "Re-anchor preserved operator priority." },
  dedupe_keys_tracked: 6,
  last_checkpoint: {
    status: "awaiting_approval",
    checkpointed_at: "2026-04-21T10:00:00Z",
  },
};

function renderHeader(overrides = {}) {
  const props = {
    autonomyStatus: STATUS_FIXTURE,
    budgets: [],
    loading: false,
    resourceError: null,
    supervisorTone: "success",
    ...overrides,
  };
  render(<AutonomyStatusHeader {...props} />);
  return props;
}

test("renders the supervisor status section title", () => {
  renderHeader();
  expect(screen.getByText("Supervisor status")).toBeInTheDocument();
});

test("shows loading message when loading and no status available", () => {
  renderHeader({ autonomyStatus: null, loading: true });
  expect(screen.getByText("Loading autonomy supervisor state…")).toBeInTheDocument();
});

test("shows error message when provided", () => {
  renderHeader({ resourceError: "Status endpoint degraded" });
  expect(screen.getByText("Status endpoint degraded")).toBeInTheDocument();
});

test("shows fallback when status is null and not loading", () => {
  renderHeader({ autonomyStatus: null, loading: false });
  expect(screen.getByText("No autonomy status returned by the backend.")).toBeInTheDocument();
});

test("renders metric cards from backend status", () => {
  renderHeader();
  expect(screen.getByText("Running")).toBeInTheDocument();
  expect(screen.getByText("Hyperfocus Review")).toBeInTheDocument();
});

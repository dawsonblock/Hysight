import { render, screen } from "@testing-library/react";
import BudgetPanel from "@/features/autonomy/components/BudgetPanel";

const BUDGET_FIXTURE = {
  agent_id: "agent-1",
  launched_runs_total: 12,
  active_runs: 2,
  total_steps_observed: 340,
  total_retries_used: 5,
  last_budget_breach_at: null,
};

function renderBudgetPanel(overrides = {}) {
  const props = {
    autonomyStatus: { kill_switch_active: false },
    budgets: [],
    resourceError: null,
    ...overrides,
  };
  render(<BudgetPanel {...props} />);
  return props;
}

test("shows empty state when no budgets returned", () => {
  renderBudgetPanel();
  expect(screen.getByText("No budget ledgers returned.")).toBeInTheDocument();
});

test("shows resource error when provided", () => {
  renderBudgetPanel({ resourceError: "Budgets degraded" });
  expect(screen.getByText("Budgets degraded")).toBeInTheDocument();
});

test("renders budget ledger row with agent id", () => {
  renderBudgetPanel({ budgets: [BUDGET_FIXTURE] });
  expect(screen.getByText("agent-1")).toBeInTheDocument();
  expect(screen.getByText("12")).toBeInTheDocument();
});

test("shows Kill switch active in Deadman column when kill switch is active", () => {
  renderBudgetPanel({
    budgets: [BUDGET_FIXTURE],
    autonomyStatus: { kill_switch_active: true },
  });
  expect(screen.getByText("Kill switch active")).toBeInTheDocument();
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EscalationsPanel from "@/features/autonomy/components/EscalationsPanel";

const ESCALATION_FIXTURE = {
  agent_id: "agent-1",
  trigger_id: "trig-1",
  run_id: "run-abc",
  status: "pending",
  last_decision: "escalate",
  checkpointed_at: "2026-04-21T10:00:00Z",
};

function renderEscalationsPanel(overrides = {}) {
  const props = {
    escalations: [],
    onOpenRun: jest.fn(),
    resourceError: null,
    ...overrides,
  };
  render(<EscalationsPanel {...props} />);
  return props;
}

test("shows empty state when no escalations returned", () => {
  renderEscalationsPanel();
  expect(screen.getByText("No escalations returned.")).toBeInTheDocument();
});

test("shows resource error when provided", () => {
  renderEscalationsPanel({ resourceError: "Escalations degraded" });
  expect(screen.getByText("Escalations degraded")).toBeInTheDocument();
});

test("Open replay button calls onOpenRun with run_id", async () => {
  const user = userEvent.setup();
  const props = renderEscalationsPanel({ escalations: [ESCALATION_FIXTURE] });

  await user.click(screen.getByRole("button", { name: "Open replay" }));
  expect(props.onOpenRun).toHaveBeenCalledWith("run-abc");
});

test("shows No run link when escalation has no run_id", () => {
  renderEscalationsPanel({
    escalations: [{ ...ESCALATION_FIXTURE, run_id: null }],
  });
  expect(screen.getByText("No run link")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Open replay" })).not.toBeInTheDocument();
});

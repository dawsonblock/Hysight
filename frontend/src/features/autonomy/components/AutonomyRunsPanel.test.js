import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AutonomyRunsPanel from "@/features/autonomy/components/AutonomyRunsPanel";

function renderAutonomyRunsPanel(overrides = {}) {
  const props = {
    autonomyRuns: [
      {
        agent_id: "agent-1",
        trigger_id: "trigger-1",
        run_id: "run-autonomy-1",
      },
    ],
    autonomyStatus: {
      kill_switch_active: false,
      last_evaluator_decision: "escalate",
    },
    escalations: [
      {
        run_id: "run-autonomy-1",
        status: "awaiting_approval",
      },
    ],
    latestCheckpointByRun: {
      "run-autonomy-1": {
        current_attention_mode: "hyperfocus_review",
        last_decision: "escalate",
        status: "awaiting_approval",
      },
    },
    onOpenRun: jest.fn(),
    resourceErrors: {
      runs: "Runs degraded",
    },
    selectedRunId: "run-autonomy-1",
    ...overrides,
  };

  render(<AutonomyRunsPanel {...props} />);

  return props;
}

test("shows degraded run-state messages and routes replay through the existing run surface", async () => {
  const user = userEvent.setup();
  const props = renderAutonomyRunsPanel();

  expect(screen.getByText("Runs degraded")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Viewing in Runs" }));

  expect(props.onOpenRun).toHaveBeenCalledWith("run-autonomy-1");
});
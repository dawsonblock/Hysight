import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CheckpointsPanel from "@/features/autonomy/components/CheckpointsPanel";

const CHECKPOINT_FIXTURE = {
  agent_id: "agent-1",
  trigger_id: "trig-1",
  run_id: "run-abc",
  status: "complete",
  attempt: 1,
  last_decision: "continue",
  current_attention_mode: "focused",
  hyperfocus_steps_used: 0,
  novelty_budget_remaining: 5,
  last_reanchor_summary: null,
  checkpointed_at: "2026-04-21T10:00:00Z",
  budget_snapshot: { style_novelty_budget: 10 },
};

function renderCheckpointsPanel(overrides = {}) {
  const props = {
    checkpoints: [],
    onOpenRun: jest.fn(),
    resourceError: null,
    ...overrides,
  };
  render(<CheckpointsPanel {...props} />);
  return props;
}

test("shows empty state when no checkpoints returned", () => {
  renderCheckpointsPanel();
  expect(screen.getByText("No checkpoints returned.")).toBeInTheDocument();
});

test("shows resource error when provided", () => {
  renderCheckpointsPanel({ resourceError: "Checkpoints degraded" });
  expect(screen.getByText("Checkpoints degraded")).toBeInTheDocument();
});

test("Replay button calls onOpenRun with run_id", async () => {
  const user = userEvent.setup();
  const props = renderCheckpointsPanel({ checkpoints: [CHECKPOINT_FIXTURE] });

  await user.click(screen.getByRole("button", { name: "Replay" }));
  expect(props.onOpenRun).toHaveBeenCalledWith("run-abc");
});

test("shows No run linked when checkpoint has no run_id", () => {
  renderCheckpointsPanel({
    checkpoints: [{ ...CHECKPOINT_FIXTURE, run_id: null }],
  });
  expect(screen.getByText("No run linked")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Replay" })).not.toBeInTheDocument();
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SchedulesPanel from "@/features/autonomy/components/SchedulesPanel";

function renderSchedulesPanel(overrides = {}) {
  const props = {
    actionKey: "",
    agents: [{ agent_id: "agent-1", name: "Release supervisor" }],
    formError: null,
    onCreateSchedule: jest.fn((event) => event.preventDefault()),
    onDisable: jest.fn(),
    onEnable: jest.fn(),
    onScheduleFormChange: jest.fn(),
    resourceError: null,
    scheduleForm: { agentId: "", intervalSeconds: "300", goalOverride: "", payload: "{}", enabled: true },
    schedules: [],
    ...overrides,
  };
  render(<SchedulesPanel {...props} />);
  return props;
}

test("shows empty state when no schedules returned", () => {
  renderSchedulesPanel();
  expect(screen.getByText("No schedules returned.")).toBeInTheDocument();
});

test("shows resource error when provided", () => {
  renderSchedulesPanel({ resourceError: "Schedules degraded" });
  expect(screen.getByText("Schedules degraded")).toBeInTheDocument();
});

test("renders schedule row with Enable and Disable buttons", async () => {
  const user = userEvent.setup();
  const props = renderSchedulesPanel({
    schedules: [
      {
        schedule_id: "schedule-1",
        agent_id: "agent-1",
        interval_seconds: 300,
        goal_override: "Check release proof drift",
        payload: { source: "operator" },
        enabled: true,
        last_fired_at: null,
      },
    ],
  });

  expect(screen.getByText("schedule-1")).toBeInTheDocument();
  expect(screen.getByText("Check release proof drift")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Disable" }));
  expect(props.onDisable).toHaveBeenCalled();
});

test("Enable button calls onEnable for a disabled schedule", async () => {
  const user = userEvent.setup();
  const props = renderSchedulesPanel({
    schedules: [
      {
        schedule_id: "schedule-2",
        agent_id: "agent-1",
        interval_seconds: 600,
        goal_override: null,
        payload: null,
        enabled: false,
        last_fired_at: null,
      },
    ],
  });

  await user.click(screen.getByRole("button", { name: "Enable" }));
  expect(props.onEnable).toHaveBeenCalled();
});

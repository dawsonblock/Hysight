import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import KillSwitchBar from "@/features/autonomy/components/KillSwitchBar";

function renderKillSwitchBar(overrides = {}) {
  const props = {
    actionKey: "",
    autonomyStatus: {
      kill_switch_active: false,
      kill_switch_reason: null,
      kill_switch_set_at: "2026-04-21T10:00:00Z",
    },
    killReason: "",
    onKillReasonChange: jest.fn(),
    onSetKillSwitch: jest.fn(),
    ...overrides,
  };

  render(<KillSwitchBar {...props} />);

  return props;
}

test("routes kill-switch activation with the operator reason", async () => {
  const user = userEvent.setup();
  const props = renderKillSwitchBar();

  fireEvent.change(
    screen.getByPlaceholderText("Operator reason recorded with kill-switch activation"),
    { target: { value: "Operator hold" } }
  );

  expect(props.onKillReasonChange).toHaveBeenCalledWith("Operator hold");
  expect(screen.getByRole("button", { name: "Clear kill switch" })).toBeDisabled();

  await user.click(screen.getByRole("button", { name: "Kill autonomy" }));

  expect(props.onSetKillSwitch).toHaveBeenCalledWith(true);
});

test("routes kill-switch clearing when the backend reports an active stop", async () => {
  const user = userEvent.setup();
  const props = renderKillSwitchBar({
    autonomyStatus: {
      kill_switch_active: true,
      kill_switch_reason: "Operator hold",
      kill_switch_set_at: "2026-04-21T10:00:00Z",
    },
    killReason: "Operator hold",
  });

  expect(screen.getByRole("button", { name: "Kill autonomy" })).toBeDisabled();

  await user.click(screen.getByRole("button", { name: "Clear kill switch" }));

  expect(props.onSetKillSwitch).toHaveBeenCalledWith(false);
});
import { render, screen } from "@testing-library/react";
import { useState } from "react";
import userEvent from "@testing-library/user-event";
import KillSwitchBar from "@/features/autonomy/components/KillSwitchBar";

function renderKillSwitchBar(overrides = {}) {
  const { onSetKillSwitch = jest.fn(), ...rest } = overrides;

  const baseProps = {
    actionKey: "",
    autonomyStatus: {
      kill_switch_active: false,
      kill_switch_reason: null,
      kill_switch_set_at: "2026-04-21T10:00:00Z",
    },
    onSetKillSwitch,
    ...rest,
  };

  function Wrapper() {
    const [killReason, setKillReason] = useState("");
    return <KillSwitchBar {...baseProps} killReason={killReason} setKillReason={setKillReason} />;
  }

  render(<Wrapper />);

  return baseProps;
}

test("opens dialog on Kill autonomy and calls onSetKillSwitch with reason", async () => {
  const user = userEvent.setup();
  const props = renderKillSwitchBar();

  expect(screen.getByRole("button", { name: "Clear kill switch" })).toBeDisabled();

  await user.click(screen.getByRole("button", { name: "Kill autonomy" }));

  expect(await screen.findByText("Activate kill switch?")).toBeInTheDocument();

  await user.type(
    screen.getByPlaceholderText("Operator reason recorded with kill-switch activation"),
    "Operator hold"
  );
  await user.click(screen.getByRole("button", { name: "Activate kill switch" }));

  expect(props.onSetKillSwitch).toHaveBeenCalledWith(true, "Operator hold");
});

test("opens dialog on Clear kill switch and calls onSetKillSwitch with null reason", async () => {
  const user = userEvent.setup();
  const props = renderKillSwitchBar({
    autonomyStatus: {
      kill_switch_active: true,
      kill_switch_reason: "Operator hold",
      kill_switch_set_at: "2026-04-21T10:00:00Z",
    },
  });

  expect(screen.getByRole("button", { name: "Kill autonomy" })).toBeDisabled();

  await user.click(screen.getByRole("button", { name: "Clear kill switch" }));

  expect(await screen.findByText("Clear kill switch?")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Confirm clear" }));

  expect(props.onSetKillSwitch).toHaveBeenCalledWith(false, null);
});

test("cancel closes the dialog without calling onSetKillSwitch", async () => {
  const user = userEvent.setup();
  const props = renderKillSwitchBar();

  await user.click(screen.getByRole("button", { name: "Kill autonomy" }));
  await screen.findByText("Activate kill switch?");

  await user.click(screen.getByRole("button", { name: "Cancel" }));

  expect(props.onSetKillSwitch).not.toHaveBeenCalled();
  expect(screen.queryByText("Activate kill switch?")).not.toBeInTheDocument();
});
import { useState } from "react";
import { toErrorMessage } from "@/lib/api";
import {
  cancelAutonomyInboxItem,
  clearAutonomyKillSwitch,
  disableAutonomySchedule,
  enableAutonomyKillSwitch,
  enableAutonomySchedule,
  pauseAutonomyAgent,
  resumeAutonomyAgent,
  stopAutonomyAgent,
} from "@/lib/autonomy-api";
import { toast } from "@/hooks/use-toast";

export default function useAutonomyActions({ refreshWorkspace }) {
  const [actionKey, setActionKey] = useState("");
  const [actionNotice, setActionNotice] = useState(
    /** @type {{ tone: string, text: string } | null} */ (null)
  );

  async function performAction(key, operation, successTitle, successDescription) {
    setActionKey(key);
    setActionNotice(null);

    try {
      await operation();
      setActionNotice({ tone: "success", text: successDescription });
      toast({ title: successTitle, description: successDescription });
      refreshWorkspace();
    } catch (error) {
      const message = toErrorMessage(error, "Action failed.");
      setActionNotice({ tone: "error", text: message });
      toast({ title: successTitle, description: message });
    } finally {
      setActionKey("");
    }
  }

  async function handleKillSwitchChange(nextActive, reason) {
    await performAction(
      nextActive ? "kill" : "unkill",
      () =>
        nextActive
          ? enableAutonomyKillSwitch({ reason: (reason || "").trim() || null })
          : clearAutonomyKillSwitch(),
      nextActive ? "Kill switch updated" : "Kill switch cleared",
      nextActive
        ? "Autonomy kill switch is now active."
        : "Autonomy kill switch is now clear."
    );
  }

  function handlePauseAgent(agent) {
    return performAction(
      `pause:${agent.agent_id}`,
      () => pauseAutonomyAgent(agent.agent_id),
      "Agent paused",
      `Paused ${agent.name}.`
    );
  }

  function handleResumeAgent(agent) {
    return performAction(
      `resume:${agent.agent_id}`,
      () => resumeAutonomyAgent(agent.agent_id),
      "Agent resumed",
      `Resumed ${agent.name}.`
    );
  }

  function handleStopAgent(agent) {
    return performAction(
      `stop:${agent.agent_id}`,
      () => stopAutonomyAgent(agent.agent_id),
      "Agent stopped",
      `Stopped ${agent.name}.`
    );
  }

  function handleEnableSchedule(schedule) {
    return performAction(
      `enable-schedule:${schedule.schedule_id}`,
      () => enableAutonomySchedule(schedule.schedule_id),
      "Schedule enabled",
      `Enabled ${schedule.schedule_id}.`
    );
  }

  function handleDisableSchedule(schedule) {
    return performAction(
      `disable-schedule:${schedule.schedule_id}`,
      () => disableAutonomySchedule(schedule.schedule_id),
      "Schedule disabled",
      `Disabled ${schedule.schedule_id}.`
    );
  }

  function handleCancelInboxItem(item) {
    return performAction(
      `cancel-inbox:${item.item_id}`,
      () => cancelAutonomyInboxItem(item.item_id),
      "Inbox item cancelled",
      `Cancelled ${item.item_id}.`
    );
  }

  return {
    actionKey,
    actionNotice,
    performAction,
    handleKillSwitchChange,
    handlePauseAgent,
    handleResumeAgent,
    handleStopAgent,
    handleEnableSchedule,
    handleDisableSchedule,
    handleCancelInboxItem,
  };
}

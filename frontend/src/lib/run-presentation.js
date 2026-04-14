export function summarizeApprovalToast(data, decision) {
  const stateLabel = data?.state ? String(data.state).replace(/_/g, " ") : "updated";
  const outcome = data?.workflow_outcome?.reason || data?.action_result?.error;
  const baseMessage = decision === "approve"
    ? `Run ${data?.run_id || ""} resumed and is now ${stateLabel}.`
    : `Run ${data?.run_id || ""} is now ${stateLabel}.`;

  return outcome ? `${baseMessage} ${outcome}` : baseMessage;
}

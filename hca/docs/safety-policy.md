## Safety policy

The runtime enforces a simple safety policy for external actions.  Each tool is registered with a risk level and a list of required approvals.  Risk levels range from `low` to `high`.

High‑risk actions must be approved by a trusted user or process before execution.  The runtime requests approval and pauses the run.  Approved actions resume execution when a valid grant token is supplied.  Denied actions result in the run being halted.

The policy also includes a proactive throttle to prevent the agent from taking unrequested actions when uncertainty is high or user burden is significant.

This policy is rudimentary and does not implement advanced moral reasoning or consent simulation.  For production systems, a richer safety model would be required.

import { z } from "zod";
import { buildQuery, encodeSegment, fetchJson } from "@/lib/api";

const looseObjectSchema = z.object({}).passthrough();

const autonomyRunLinkSchema = z.object({
  agent_id: z.string(),
  trigger_id: z.string(),
  run_id: z.string(),
  run_status: z.string().optional(),
  last_state: z.string().nullable().optional(),
  last_decision: z.string().nullable().optional(),
}).passthrough();

const autonomyBudgetLedgerSchema = z.object({
  agent_id: z.string(),
  launched_runs_total: z.number().int().nonnegative().optional(),
  active_runs: z.number().int().nonnegative().optional(),
  total_steps_observed: z.number().int().nonnegative().optional(),
  total_retries_used: z.number().int().nonnegative().optional(),
  last_run_started_at: z.string().nullish(),
  last_run_completed_at: z.string().nullish(),
  last_budget_breach_at: z.string().nullish(),
  updated_at: z.string().nullish(),
}).passthrough();

const autonomyCheckpointSchema = z.object({
  agent_id: z.string(),
  trigger_id: z.string(),
  run_id: z.string().nullable().optional(),
  status: z.string(),
  attempt: z.number().int().nonnegative(),
  last_event_id: z.string().nullable().optional(),
  last_state: z.string().nullable().optional(),
  last_decision: z.string().nullable().optional(),
  resume_allowed: z.boolean().optional(),
  safe_to_continue: z.boolean().optional(),
  kill_switch_observed: z.boolean().optional(),
  idempotency: z.string().nullable().optional(),
  dedupe_key: z.string().nullable().optional(),
  style_profile_id: z.string().optional(),
  current_attention_mode: z.string().nullable().optional(),
  current_subgoal: z.string().nullable().optional(),
  interrupt_queue_length: z.number().int().nonnegative().optional(),
  reanchor_due: z.boolean().optional(),
  novelty_budget_remaining: z.number().int().nonnegative().nullable().optional(),
  hyperfocus_steps_used: z.number().int().nonnegative().optional(),
  last_reanchor_summary: looseObjectSchema.nullish(),
  checkpointed_at: z.string(),
  budget_snapshot: z.record(z.unknown()).optional(),
}).passthrough();

const autonomySubsystemSchema = z.object({
  enabled: z.boolean(),
  running: z.boolean(),
  active_agents: z.number().int().nonnegative(),
  active_runs: z.number().int().nonnegative(),
  pending_triggers: z.number().int().nonnegative(),
  pending_escalations: z.number().int().nonnegative().optional(),
  loop_running: z.boolean().optional(),
  kill_switch_active: z.boolean().optional(),
  kill_switch_reason: z.string().nullable().optional(),
  kill_switch_set_at: z.string().nullable().optional(),
  last_tick_at: z.string().nullable().optional(),
  last_error: z.string().nullable().optional(),
  last_evaluator_decision: z.string().nullable().optional(),
  current_attention_mode: z.string().nullable().optional(),
  interrupt_queue_length: z.number().int().nonnegative().optional(),
  reanchor_due: z.boolean().optional(),
  novelty_budget_remaining: z.number().int().nonnegative().nullable().optional(),
  hyperfocus_steps_used: z.number().int().nonnegative().optional(),
  last_reanchor_summary: looseObjectSchema.nullish(),
  dedupe_keys_tracked: z.number().int().nonnegative().optional(),
  recent_runs: z.array(autonomyRunLinkSchema).optional(),
  budget_ledgers: z.array(autonomyBudgetLedgerSchema).optional(),
  last_checkpoint: autonomyCheckpointSchema.nullish(),
}).passthrough();

const autonomyBudgetModelSchema = z.object({
  max_steps_per_run: z.number().int().nonnegative().optional(),
  max_runs_per_agent: z.number().int().nonnegative().optional(),
  max_parallel_runs: z.number().int().nonnegative().optional(),
  max_retries_per_step: z.number().int().nonnegative().optional(),
  max_run_duration_seconds: z.number().int().nonnegative().optional(),
  deadman_timeout_seconds: z.number().int().nonnegative().optional(),
}).passthrough();

const autonomyPolicySchema = z.object({
  mode: z.string(),
  enabled: z.boolean(),
  budget: autonomyBudgetModelSchema,
  approval_required_action_classes: z.array(z.string()).optional(),
  allowed_tool_names: z.array(z.string()).optional(),
  allowed_network_domains: z.array(z.string()).optional(),
  allowed_workspace_roots: z.array(z.string()).optional(),
  allow_memory_writes: z.boolean().optional(),
  allow_external_writes: z.boolean().optional(),
  auto_resume_after_approval: z.boolean().optional(),
}).passthrough();

const autonomyAgentSchema = z.object({
  agent_id: z.string(),
  name: z.string(),
  description: z.string().nullable().optional(),
  mode: z.string(),
  status: z.string(),
  style_profile_id: z.string(),
  policy: autonomyPolicySchema,
  created_at: z.string(),
  updated_at: z.string(),
}).passthrough();

const autonomyAgentListSchema = z.object({
  agents: z.array(autonomyAgentSchema),
}).passthrough();

const autonomyScheduleSchema = z.object({
  schedule_id: z.string(),
  agent_id: z.string(),
  interval_seconds: z.number().int().positive(),
  goal_override: z.string().nullable().optional(),
  payload: z.record(z.unknown()).optional(),
  enabled: z.boolean(),
  last_fired_at: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
}).passthrough();

const autonomyScheduleListSchema = z.object({
  schedules: z.array(autonomyScheduleSchema),
}).passthrough();

const autonomyInboxItemSchema = z.object({
  item_id: z.string(),
  agent_id: z.string(),
  goal: z.string(),
  payload: z.record(z.unknown()).optional(),
  status: z.string(),
  created_at: z.string(),
  claimed_at: z.string().nullable().optional(),
}).passthrough();

const autonomyInboxListSchema = z.object({
  items: z.array(autonomyInboxItemSchema),
}).passthrough();

const autonomyRunListSchema = z.object({
  runs: z.array(autonomyRunLinkSchema),
}).passthrough();

const autonomyKillSwitchSchema = z.object({
  active: z.boolean(),
  reason: z.string().nullable().optional(),
  set_at: z.string().nullable().optional(),
  cleared_at: z.string().nullable().optional(),
  set_by: z.string().nullable().optional(),
}).passthrough();

const autonomyControlResponseSchema = z.object({
  agent_id: z.string(),
  status: z.string(),
}).passthrough();

const autonomyBudgetLedgerListSchema = z.object({
  ledgers: z.array(autonomyBudgetLedgerSchema),
}).passthrough();

const autonomyEscalationSchema = z.object({
  agent_id: z.string(),
  trigger_id: z.string(),
  run_id: z.string().nullable().optional(),
  status: z.string(),
  last_state: z.string().nullable().optional(),
  last_decision: z.string().nullable().optional(),
  checkpointed_at: z.string(),
}).passthrough();

const autonomyEscalationListSchema = z.object({
  escalations: z.array(autonomyEscalationSchema),
}).passthrough();

const autonomyCheckpointListSchema = z.object({
  checkpoints: z.array(autonomyCheckpointSchema),
}).passthrough();

const autonomyWorkspaceSnapshotSchema = z.object({
  snapshot_at: z.string(),
  status: autonomySubsystemSchema.nullish(),
  agents: z.array(autonomyAgentSchema).optional(),
  schedules: z.array(autonomyScheduleSchema).optional(),
  inbox: z.array(autonomyInboxItemSchema).optional(),
  runs: z.array(autonomyRunLinkSchema).optional(),
  escalations: z.array(autonomyEscalationSchema).optional(),
  budgets: z.array(autonomyBudgetLedgerSchema).optional(),
  checkpoints: z.array(autonomyCheckpointSchema).optional(),
  section_errors: z.record(z.string()).optional(),
}).passthrough();

export function getAutonomyStatus() {
  return fetchJson("/hca/autonomy/status", undefined, autonomySubsystemSchema);
}

export function enableAutonomyKillSwitch({ reason, setBy = "operator_ui" } = {}) {
  return fetchJson(
    "/hca/autonomy/kill",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active: true, reason: reason || null, set_by: setBy }),
    },
    autonomyKillSwitchSchema
  );
}

export function clearAutonomyKillSwitch({ setBy = "operator_ui" } = {}) {
  return fetchJson(
    "/hca/autonomy/unkill",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active: false, reason: null, set_by: setBy }),
    },
    autonomyKillSwitchSchema
  );
}

export function listAutonomyAgents() {
  return fetchJson("/hca/autonomy/agents", undefined, autonomyAgentListSchema);
}

export function createAutonomyAgent(payload) {
  return fetchJson(
    "/hca/autonomy/agents",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    autonomyAgentSchema
  );
}

export function getAutonomyAgent(agentId) {
  return fetchJson(
    `/hca/autonomy/agents/${encodeSegment(agentId)}`,
    undefined,
    autonomyAgentSchema
  );
}

function postAutonomyAgentAction(agentId, action) {
  return fetchJson(
    `/hca/autonomy/agents/${encodeSegment(agentId)}/${encodeSegment(action)}`,
    { method: "POST" },
    autonomyControlResponseSchema
  );
}

export function pauseAutonomyAgent(agentId) {
  return postAutonomyAgentAction(agentId, "pause");
}

export function resumeAutonomyAgent(agentId) {
  return postAutonomyAgentAction(agentId, "resume");
}

export function stopAutonomyAgent(agentId) {
  return postAutonomyAgentAction(agentId, "stop");
}

export function listAutonomySchedules() {
  return fetchJson("/hca/autonomy/schedules", undefined, autonomyScheduleListSchema);
}

export function createAutonomySchedule(payload) {
  return fetchJson(
    "/hca/autonomy/schedules",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    autonomyScheduleSchema
  );
}

function postAutonomyScheduleAction(scheduleId, action) {
  return fetchJson(
    `/hca/autonomy/schedules/${encodeSegment(scheduleId)}/${encodeSegment(action)}`,
    { method: "POST" },
    autonomyScheduleSchema
  );
}

export function enableAutonomySchedule(scheduleId) {
  return postAutonomyScheduleAction(scheduleId, "enable");
}

export function disableAutonomySchedule(scheduleId) {
  return postAutonomyScheduleAction(scheduleId, "disable");
}

export function listAutonomyInbox({ agentId, status } = {}) {
  return fetchJson(
    `/hca/autonomy/inbox${buildQuery({ agent_id: agentId, status })}`,
    undefined,
    autonomyInboxListSchema
  );
}

export function createAutonomyInboxItem(payload) {
  return fetchJson(
    "/hca/autonomy/inbox",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    autonomyInboxItemSchema
  );
}

export function cancelAutonomyInboxItem(itemId) {
  return fetchJson(
    `/hca/autonomy/inbox/${encodeSegment(itemId)}/cancel`,
    { method: "POST" },
    autonomyInboxItemSchema
  );
}

export function listAutonomyCheckpoints(agentId) {
  const basePath = agentId
    ? `/hca/autonomy/checkpoints/${encodeSegment(agentId)}`
    : "/hca/autonomy/checkpoints";

  return fetchJson(basePath, undefined, autonomyCheckpointListSchema);
}

export function listAutonomyRuns() {
  return fetchJson("/hca/autonomy/runs", undefined, autonomyRunListSchema);
}

export function listAutonomyBudgets() {
  return fetchJson("/hca/autonomy/budgets", undefined, autonomyBudgetLedgerListSchema);
}

export function listAutonomyEscalations() {
  return fetchJson("/hca/autonomy/escalations", undefined, autonomyEscalationListSchema);
}

export function getAutonomyWorkspace() {
  return fetchJson("/hca/autonomy/workspace", undefined, autonomyWorkspaceSnapshotSchema);
}
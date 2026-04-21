import { z } from "zod";

const configuredBackendUrl = process.env.REACT_APP_BACKEND_URL?.trim();
const normalizedBackendUrl = configuredBackendUrl
  ? configuredBackendUrl.replace(/\/+$/, "")
  : "";

export const API_BASE_URL = normalizedBackendUrl
  ? `${normalizedBackendUrl}/api`
  : "/api";

const looseObjectSchema = z.object({}).passthrough();

const actionBindingSchema = z.object({
  tool_name: z.string(),
  target: z.string().nullable().optional(),
  normalized_arguments: z.record(z.unknown()).optional(),
  action_class: z.string().nullable().optional(),
  requires_approval: z.boolean().optional(),
  policy_snapshot: z.record(z.unknown()).optional(),
  policy_fingerprint: z.string().optional(),
  action_fingerprint: z.string().optional(),
}).passthrough();

const approvalRequestSchema = z.object({
  approval_id: z.string(),
  action_id: z.string().optional(),
  action_kind: z.string().nullable().optional(),
  action_class: z.string().nullable().optional(),
  binding: actionBindingSchema.nullish(),
  reason: z.string().optional(),
  requested_at: z.string().nullish(),
  expires_at: z.string().nullish(),
}).passthrough();

const approvalDecisionSchema = z.object({
  approval_id: z.string(),
  decision: z.string(),
  actor: z.string().optional(),
  reason: z.string().nullable().optional(),
  binding: actionBindingSchema.nullish(),
  decided_at: z.string().nullish(),
  expires_at: z.string().nullish(),
}).passthrough();

const approvalGrantSchema = z.object({
  approval_id: z.string(),
  token: z.string().optional(),
  actor: z.string().optional(),
  binding: actionBindingSchema.nullish(),
  granted_at: z.string().nullish(),
  expires_at: z.string().nullish(),
}).passthrough();

const approvalConsumptionSchema = z.object({
  approval_id: z.string(),
  token: z.string().optional(),
  binding: actionBindingSchema.nullish(),
  consumed_at: z.string().nullish(),
}).passthrough();

const approvalSchema = z.object({
  approval_id: z.string(),
  status: z.string(),
  expired: z.boolean().optional(),
  request: approvalRequestSchema.nullish(),
  decision: approvalDecisionSchema.nullish(),
  grant: approvalGrantSchema.nullish(),
  consumption: approvalConsumptionSchema.nullish(),
  corruption_count: z.number().int().nonnegative().optional(),
}).passthrough();

const databaseSubsystemSchema = z.object({
  enabled: z.boolean(),
  status: z.string(),
  detail: z.string(),
  mongo_status_mode: z.string(),
  mongo_scope: z.string(),
}).passthrough();

const memorySubsystemSchema = z.object({
  backend: z.string(),
  uses_sidecar: z.boolean(),
  status: z.string(),
  detail: z.string(),
  memory_backend_mode: z.string(),
  service_available: z.boolean().nullable().optional(),
  service_url: z.string().nullable().optional(),
}).passthrough();

const storageSubsystemSchema = z.object({
  status: z.string(),
  detail: z.string(),
  root: z.string(),
  memory_dir: z.string(),
}).passthrough();

const llmSubsystemSchema = z.object({
  status: z.string(),
  detail: z.string(),
}).passthrough();

const autonomyRunLinkSchema = z.object({
  agent_id: z.string(),
  trigger_id: z.string(),
  run_id: z.string(),
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

const autonomyStatusSchema = autonomySubsystemSchema;

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

const subsystemsResponseSchema = z.object({
  status: z.string(),
  consistency_check_passed: z.boolean(),
  replay_authority: z.string(),
  hca_runtime_authority: z.string(),
  database: databaseSubsystemSchema,
  memory: memorySubsystemSchema,
  storage: storageSubsystemSchema,
  llm: llmSubsystemSchema,
  autonomy: autonomySubsystemSchema.optional(),
}).passthrough();

const runSummarySchema = z.object({
  run_id: z.string(),
  goal: z.string(),
  state: z.string(),
  plan: looseObjectSchema.optional(),
  perception: looseObjectSchema.optional(),
  critique: looseObjectSchema.optional(),
  action_taken: looseObjectSchema.optional(),
  action_result: looseObjectSchema.optional(),
  latest_receipt: looseObjectSchema.nullish(),
  active_workflow: looseObjectSchema.nullish(),
  workflow_budget: looseObjectSchema.nullish(),
  workflow_checkpoint: looseObjectSchema.nullish(),
  workflow_outcome: looseObjectSchema.nullish(),
  workflow_step_history: z.array(looseObjectSchema).optional(),
  workflow_artifacts: z.array(looseObjectSchema).optional(),
  memory_hits: z.array(looseObjectSchema).optional(),
  key_events: z.array(looseObjectSchema).optional(),
  discrepancies: z.array(z.string()).optional(),
  memory_counts: z.record(z.number()).optional(),
  memory_outcomes: z.record(z.unknown()).optional(),
  artifacts_count: z.number().int().nonnegative().optional(),
  event_count: z.number().int().nonnegative().optional(),
  approval_id: z.string().nullable().optional(),
  approval: approvalSchema.nullish(),
  last_approval_decision: z.string().nullable().optional(),
  metrics: looseObjectSchema.optional(),
}).passthrough();

const runListSchema = z.object({
  records: z.array(runSummarySchema),
  total: z.number().int().nonnegative(),
}).passthrough();

const runEventSchema = z.object({
  event_id: z.string(),
  run_id: z.string(),
  event_type: z.string(),
  summary: z.string(),
  payload: z.record(z.unknown()).optional(),
  actor: z.string().nullable().optional(),
  prior_state: z.string().nullable().optional(),
  next_state: z.string().nullable().optional(),
  is_key_event: z.boolean().optional(),
}).passthrough();

const runEventListSchema = z.object({
  run_id: z.string(),
  records: z.array(runEventSchema),
  total: z.number().int().nonnegative(),
}).passthrough();

const runArtifactSchema = z.object({
  artifact_id: z.string(),
  run_id: z.string(),
  action_id: z.string(),
  kind: z.string(),
  path: z.string(),
  source_action_ids: z.array(z.string()).optional(),
  file_paths: z.array(z.string()).optional(),
  hashes: z.record(z.string()).optional(),
  approval_id: z.string().nullable().optional(),
  workflow_id: z.string().nullable().optional(),
  metadata: z.record(z.unknown()).optional(),
  content_available: z.boolean().optional(),
}).passthrough();

const runArtifactListSchema = z.object({
  run_id: z.string(),
  records: z.array(runArtifactSchema),
  total: z.number().int().nonnegative(),
}).passthrough();

const runArtifactDetailSchema = runArtifactSchema.extend({
  content: z.string().nullable().optional(),
  size_bytes: z.number().int().nonnegative().optional(),
  truncated: z.boolean().optional(),
});

const memoryRecordSchema = z.object({
  memory_id: z.string(),
  text: z.string(),
  memory_type: z.string().nullable().optional(),
  run_id: z.string().nullable().optional(),
  stored_at: z.string().nullable().optional(),
}).passthrough();

const memoryListSchema = z.object({
  records: z.array(memoryRecordSchema),
  total: z.number().int().nonnegative(),
}).passthrough();

const deleteMemorySchema = z.object({
  deleted: z.boolean(),
  memory_id: z.string(),
}).passthrough();

function encodeSegment(value) {
  return encodeURIComponent(String(value));
}

function buildQuery(paramsObject = {}) {
  const params = new URLSearchParams();

  Object.entries(paramsObject).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }

    params.set(key, String(value));
  });

  const query = params.toString();
  return query ? `?${query}` : "";
}

function normalizePath(path) {
  return path.startsWith("/") ? path : `/${path}`;
}

export function apiUrl(path) {
  return `${API_BASE_URL}${normalizePath(path)}`;
}

async function readResponseBody(response) {
  const text = await response.text();

  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function formatErrorMessage(response, payload) {
  if (typeof payload === "string" && payload.trim()) {
    return payload.trim();
  }

  if (payload && typeof payload === "object") {
    if (typeof payload.detail === "string") {
      return payload.detail;
    }

    if (payload.detail) {
      return JSON.stringify(payload.detail);
    }

    if (typeof payload.message === "string") {
      return payload.message;
    }
  }

  const statusText = response.statusText || "Request failed";
  return `${statusText} (${response.status})`;
}

export function apiFetch(path, init) {
  return fetch(apiUrl(path), init);
}

export async function getResponseErrorMessage(response) {
  return formatErrorMessage(response, await readResponseBody(response));
}

export async function fetchJson(path, init, schema) {
  const response = await apiFetch(path, init);
  const payload = await readResponseBody(response);

  if (!response.ok) {
    throw new Error(formatErrorMessage(response, payload));
  }

  if (!schema) {
    return payload;
  }

  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    const firstIssue = parsed.error.issues[0];
    const issuePath = firstIssue?.path?.length
      ? firstIssue.path.join(".")
      : "response";
    throw new Error(
      `Unexpected response shape from ${normalizePath(path)} at ${issuePath}: ${firstIssue?.message || "invalid payload"}`
    );
  }

  return parsed.data;
}

export function toErrorMessage(error, fallback = "Request failed.") {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
}

export function streamRun(goal) {
  return apiFetch("/hca/run/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ goal }),
  });
}

export function decideRunApproval(runId, decision, approvalId) {
  return fetchJson(
    `/hca/run/${encodeSegment(runId)}/${encodeSegment(decision)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approval_id: approvalId }),
    },
    runSummarySchema
  );
}

export function getSubsystems() {
  return fetchJson("/subsystems", undefined, subsystemsResponseSchema);
}

export function listRuns({ query, limit, offset }) {
  return fetchJson(
    `/hca/runs${buildQuery({
      q: typeof query === "string" ? query.trim() : undefined,
      limit,
      offset,
    })}`,
    undefined,
    runListSchema
  );
}

export function getRunSummary(runId) {
  return fetchJson(`/hca/run/${encodeSegment(runId)}`, undefined, runSummarySchema);
}

export function listRunEvents(runId, { limit, offset } = {}) {
  return fetchJson(
    `/hca/run/${encodeSegment(runId)}/events${buildQuery({
      limit,
      offset,
    })}`,
    undefined,
    runEventListSchema
  );
}

export function listRunArtifacts(runId, { limit, offset } = {}) {
  return fetchJson(
    `/hca/run/${encodeSegment(runId)}/artifacts${buildQuery({
      limit,
      offset,
    })}`,
    undefined,
    runArtifactListSchema
  );
}

export function getRunArtifactDetail(
  runId,
  artifactId,
  { previewBytes } = {}
) {
  return fetchJson(
    `/hca/run/${encodeSegment(runId)}/artifacts/${encodeSegment(
      artifactId
    )}${buildQuery({ preview_bytes: previewBytes })}`,
    undefined,
    runArtifactDetailSchema
  );
}

export function listMemories({
  memoryType,
  scope,
  includeExpired,
  limit,
  offset,
} = {}) {
  return fetchJson(
    `/hca/memory/list${buildQuery({
      memory_type: memoryType,
      scope,
      include_expired: includeExpired ? true : undefined,
      limit,
      offset,
    })}`,
    undefined,
    memoryListSchema
  );
}

export function deleteMemoryRecord(memoryId) {
  return fetchJson(`/hca/memory/${encodeSegment(memoryId)}`, {
    method: "DELETE",
  }, deleteMemorySchema);
}

export function getAutonomyStatus() {
  return fetchJson("/hca/autonomy/status", undefined, autonomyStatusSchema);
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
  return fetchJson(
    "/hca/autonomy/schedules",
    undefined,
    autonomyScheduleListSchema
  );
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
  return fetchJson(
    "/hca/autonomy/budgets",
    undefined,
    autonomyBudgetLedgerListSchema
  );
}

export function listAutonomyEscalations() {
  return fetchJson(
    "/hca/autonomy/escalations",
    undefined,
    autonomyEscalationListSchema
  );
}
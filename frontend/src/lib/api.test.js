import {
  DELETE_MEMORY_FIXTURE,
  MEMORY_LIST_FIXTURE,
  RUN_APPROVED_SUMMARY_FIXTURE,
  RUN_ARTIFACT_DETAIL_FIXTURE,
  RUN_ARTIFACTS_FIXTURE,
  RUN_EVENTS_FIXTURE,
  RUN_LIST_FIXTURE,
  RUN_SUMMARY_FIXTURE,
  SUBSYSTEMS_FIXTURE,
} from "@/lib/api.fixtures";

function loadApiModule(backendUrl) {
  jest.resetModules();

  if (backendUrl === undefined) {
    delete process.env.REACT_APP_BACKEND_URL;
  } else {
    process.env.REACT_APP_BACKEND_URL = backendUrl;
  }

  return require("@/lib/api");
}

function createJsonResponse(payload, { ok = true, status = 200, statusText = "OK" } = {}) {
  return {
    ok,
    status,
    statusText,
    text: jest.fn().mockResolvedValue(JSON.stringify(payload)),
  };
}

describe("frontend API client boundary", () => {
  const originalFetch = global.fetch;
  const originalBackendUrl = process.env.REACT_APP_BACKEND_URL;

  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    if (originalBackendUrl === undefined) {
      delete process.env.REACT_APP_BACKEND_URL;
    } else {
      process.env.REACT_APP_BACKEND_URL = originalBackendUrl;
    }

    global.fetch = originalFetch;
    jest.clearAllMocks();
  });

  test("normalizes the configured backend URL into the shared API base", () => {
    const { API_BASE_URL, apiUrl } = loadApiModule("https://backend.example.test///");

    expect(API_BASE_URL).toBe("https://backend.example.test/api");
    expect(apiUrl("hca/run")).toBe("https://backend.example.test/api/hca/run");
  });

  test("listRuns sends the canonical query parameters and validates the response", async () => {
    const { listRuns } = loadApiModule();

    global.fetch.mockResolvedValue(createJsonResponse(RUN_LIST_FIXTURE));

    await expect(
      listRuns({ query: " release ", limit: 5, offset: 10 })
    ).resolves.toEqual(RUN_LIST_FIXTURE);

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/hca/runs?q=release&limit=5&offset=10",
      undefined
    );
  });

  test("getRunSummary validates a realistic replay-backed run payload", async () => {
    const { getRunSummary } = loadApiModule();

    global.fetch.mockResolvedValue(createJsonResponse(RUN_SUMMARY_FIXTURE));

    await expect(getRunSummary("run-completed")).resolves.toEqual(RUN_SUMMARY_FIXTURE);

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/hca/run/run-completed",
      undefined
    );
  });

  test("decideRunApproval posts to the canonical approval route and validates the summary", async () => {
    const { decideRunApproval } = loadApiModule();

    global.fetch.mockResolvedValue(createJsonResponse(RUN_APPROVED_SUMMARY_FIXTURE));

    await expect(
      decideRunApproval("run-awaiting", "approve", "approval-1")
    ).resolves.toMatchObject({
      run_id: "run-awaiting",
      state: "completed",
      approval_id: "approval-1",
      last_approval_decision: "granted",
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/hca/run/run-awaiting/approve",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_id: "approval-1" }),
      })
    );
  });

  test("listRunEvents validates the event boundary", async () => {
    const { listRunEvents } = loadApiModule();

    global.fetch.mockResolvedValue(createJsonResponse(RUN_EVENTS_FIXTURE));

    await expect(listRunEvents("run-completed", { limit: 25, offset: 5 })).resolves.toEqual(
      RUN_EVENTS_FIXTURE
    );

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/hca/run/run-completed/events?limit=25&offset=5",
      undefined
    );
  });

  test("artifact list and detail helpers validate realistic payloads", async () => {
    const { getRunArtifactDetail, listRunArtifacts } = loadApiModule();

    global.fetch
      .mockResolvedValueOnce(createJsonResponse(RUN_ARTIFACTS_FIXTURE))
      .mockResolvedValueOnce(createJsonResponse(RUN_ARTIFACT_DETAIL_FIXTURE));

    await expect(listRunArtifacts("run-completed", { limit: 10, offset: 0 })).resolves.toEqual(
      RUN_ARTIFACTS_FIXTURE
    );
    await expect(
      getRunArtifactDetail("run-completed", "artifact-1", { previewBytes: 4096 })
    ).resolves.toEqual(RUN_ARTIFACT_DETAIL_FIXTURE);

    expect(global.fetch).toHaveBeenNthCalledWith(
      1,
      "/api/hca/run/run-completed/artifacts?limit=10&offset=0",
      undefined
    );
    expect(global.fetch).toHaveBeenNthCalledWith(
      2,
      "/api/hca/run/run-completed/artifacts/artifact-1?preview_bytes=4096",
      undefined
    );
  });

  test("getSubsystems reads the canonical subsystem endpoint and validates the response", async () => {
    const { getSubsystems } = loadApiModule();

    global.fetch.mockResolvedValue(createJsonResponse(SUBSYSTEMS_FIXTURE));

    await expect(getSubsystems()).resolves.toMatchObject({
      status: "degraded",
      consistency_check_passed: true,
      replay_authority: "local_store",
      hca_runtime_authority: "python_hca_runtime",
      database: {
        mongo_status_mode: "disabled",
        mongo_scope: "status_only",
      },
      memory: {
        backend: "python",
        memory_backend_mode: "local",
        status: "healthy",
      },
      storage: {
        status: "writable",
      },
    });

    expect(global.fetch).toHaveBeenCalledWith("/api/subsystems", undefined);
  });

  test("memory list and delete helpers validate realistic payloads", async () => {
    const { deleteMemoryRecord, listMemories } = loadApiModule();

    global.fetch
      .mockResolvedValueOnce(createJsonResponse(MEMORY_LIST_FIXTURE))
      .mockResolvedValueOnce(createJsonResponse(DELETE_MEMORY_FIXTURE));

    await expect(
      listMemories({ memoryType: "procedure", scope: "shared", limit: 20, offset: 2 })
    ).resolves.toEqual(MEMORY_LIST_FIXTURE);
    await expect(deleteMemoryRecord("memory-1")).resolves.toEqual(DELETE_MEMORY_FIXTURE);

    expect(global.fetch).toHaveBeenNthCalledWith(
      1,
      "/api/hca/memory/list?memory_type=procedure&scope=shared&limit=20&offset=2",
      undefined
    );
    expect(global.fetch).toHaveBeenNthCalledWith(
      2,
      "/api/hca/memory/memory-1",
      { method: "DELETE" }
    );
  });

  test("autonomy status and agent list helpers validate dedicated backend routes", async () => {
    const { getAutonomyStatus, listAutonomyAgents } = loadApiModule();

    global.fetch
      .mockResolvedValueOnce(
        createJsonResponse({
          enabled: true,
          running: true,
          active_agents: 1,
          active_runs: 1,
          pending_triggers: 2,
          pending_escalations: 1,
          loop_running: true,
          kill_switch_active: false,
          kill_switch_reason: null,
          kill_switch_set_at: null,
          last_tick_at: "2026-04-21T10:00:00Z",
          last_error: null,
          last_evaluator_decision: "escalate",
          current_attention_mode: "hyperfocus_review",
          interrupt_queue_length: 2,
          reanchor_due: true,
          novelty_budget_remaining: 4,
          hyperfocus_steps_used: 3,
          last_reanchor_summary: { summary: "Re-anchor complete" },
          dedupe_keys_tracked: 6,
          recent_runs: [
            {
              agent_id: "agent-1",
              trigger_id: "trigger-1",
              run_id: "run-autonomy-1",
            },
          ],
          budget_ledgers: [],
          last_checkpoint: null,
        })
      )
      .mockResolvedValueOnce(
        createJsonResponse({
          agents: [
            {
              agent_id: "agent-1",
              name: "Release supervisor",
              description: "Release watchdog",
              mode: "bounded",
              status: "active",
              style_profile_id: "conservative_operator",
              policy: {
                mode: "bounded",
                enabled: true,
                budget: {
                  max_steps_per_run: 50,
                  max_runs_per_agent: 25,
                  max_parallel_runs: 1,
                  max_retries_per_step: 2,
                  max_run_duration_seconds: 900,
                  deadman_timeout_seconds: 1800,
                },
                allow_memory_writes: true,
                allow_external_writes: false,
                auto_resume_after_approval: false,
              },
              created_at: "2026-04-21T09:50:00Z",
              updated_at: "2026-04-21T10:00:00Z",
            },
          ],
        })
      );

    await expect(getAutonomyStatus()).resolves.toMatchObject({
      running: true,
      current_attention_mode: "hyperfocus_review",
    });
    await expect(listAutonomyAgents()).resolves.toMatchObject({
      agents: [
        expect.objectContaining({
          agent_id: "agent-1",
          style_profile_id: "conservative_operator",
        }),
      ],
    });

    expect(global.fetch).toHaveBeenNthCalledWith(
      1,
      "/api/hca/autonomy/status",
      undefined
    );
    expect(global.fetch).toHaveBeenNthCalledWith(
      2,
      "/api/hca/autonomy/agents",
      undefined
    );
  });

  test("autonomy kill switch and agent action helpers post to canonical control routes", async () => {
    const {
      enableAutonomyKillSwitch,
      clearAutonomyKillSwitch,
      pauseAutonomyAgent,
      resumeAutonomyAgent,
      stopAutonomyAgent,
    } = loadApiModule();

    global.fetch
      .mockResolvedValueOnce(
        createJsonResponse({
          active: true,
          reason: "Operator hold",
          set_at: "2026-04-21T10:00:00Z",
          cleared_at: null,
          set_by: "operator_ui",
        })
      )
      .mockResolvedValueOnce(
        createJsonResponse({
          active: false,
          reason: null,
          set_at: "2026-04-21T10:00:00Z",
          cleared_at: "2026-04-21T10:02:00Z",
          set_by: "operator_ui",
        })
      )
      .mockResolvedValue(createJsonResponse({ agent_id: "agent-1", status: "paused" }));

    await expect(
      enableAutonomyKillSwitch({ reason: "Operator hold" })
    ).resolves.toMatchObject({ active: true, reason: "Operator hold" });
    await expect(clearAutonomyKillSwitch()).resolves.toMatchObject({ active: false });
    await expect(pauseAutonomyAgent("agent-1")).resolves.toMatchObject({ status: "paused" });
    await expect(resumeAutonomyAgent("agent-1")).resolves.toMatchObject({ status: "paused" });
    await expect(stopAutonomyAgent("agent-1")).resolves.toMatchObject({ status: "paused" });

    expect(global.fetch).toHaveBeenNthCalledWith(
      1,
      "/api/hca/autonomy/kill",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          active: true,
          reason: "Operator hold",
          set_by: "operator_ui",
        }),
      })
    );
    expect(global.fetch).toHaveBeenNthCalledWith(
      2,
      "/api/hca/autonomy/unkill",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          active: false,
          reason: null,
          set_by: "operator_ui",
        }),
      })
    );
    expect(global.fetch).toHaveBeenNthCalledWith(
      3,
      "/api/hca/autonomy/agents/agent-1/pause",
      { method: "POST" }
    );
    expect(global.fetch).toHaveBeenNthCalledWith(
      4,
      "/api/hca/autonomy/agents/agent-1/resume",
      { method: "POST" }
    );
    expect(global.fetch).toHaveBeenNthCalledWith(
      5,
      "/api/hca/autonomy/agents/agent-1/stop",
      { method: "POST" }
    );
  });

  test("fetchJson rejects an unexpected response shape from the backend boundary", async () => {
    const { fetchJson } = loadApiModule();
    const { z } = require("zod");

    global.fetch.mockResolvedValue(
      createJsonResponse({ run_id: 7 })
    );

    await expect(
      fetchJson(
        "/hca/run/run-1",
        undefined,
        z.object({ run_id: z.string() })
      )
    ).rejects.toThrow(
      "Unexpected response shape from /hca/run/run-1 at run_id"
    );
  });
});
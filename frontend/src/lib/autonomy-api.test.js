function loadAutonomyApiModule(backendUrl) {
  jest.resetModules();

  if (backendUrl === undefined) {
    delete process.env.REACT_APP_BACKEND_URL;
  } else {
    process.env.REACT_APP_BACKEND_URL = backendUrl;
  }

  return require("@/lib/autonomy-api");
}

function createJsonResponse(payload, { ok = true, status = 200, statusText = "OK" } = {}) {
  return {
    ok,
    status,
    statusText,
    text: jest.fn().mockResolvedValue(JSON.stringify(payload)),
  };
}

describe("autonomy API client boundary", () => {
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

  test("autonomy status and agent list helpers validate dedicated backend routes", async () => {
    const { getAutonomyStatus, listAutonomyAgents } = loadAutonomyApiModule();

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
      clearAutonomyKillSwitch,
      enableAutonomyKillSwitch,
      pauseAutonomyAgent,
      resumeAutonomyAgent,
      stopAutonomyAgent,
    } = loadAutonomyApiModule();

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

  test("getAutonomyWorkspace fetches the aggregate snapshot endpoint", async () => {
    const { getAutonomyWorkspace } = loadAutonomyApiModule();

    const snapshotPayload = {
      snapshot_at: "2026-04-21T10:00:00Z",
      status: {
        enabled: true,
        running: false,
        active_agents: 0,
        active_runs: 0,
        pending_triggers: 0,
      },
      agents: [],
      schedules: [],
      inbox: [],
      runs: [],
      escalations: [],
      budgets: [],
      checkpoints: [],
      section_errors: {},
    };

    global.fetch.mockResolvedValueOnce(createJsonResponse(snapshotPayload));

    const result = await getAutonomyWorkspace();

    expect(result).toMatchObject({
      snapshot_at: "2026-04-21T10:00:00Z",
      section_errors: {},
      agents: [],
    });
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/hca/autonomy/workspace",
      undefined
    );
  });
});
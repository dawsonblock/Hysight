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
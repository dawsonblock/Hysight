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

    global.fetch.mockResolvedValue(
      createJsonResponse({
        records: [{ run_id: "run-1", goal: "Inspect release", state: "completed" }],
        total: 1,
      })
    );

    await expect(
      listRuns({ query: " release ", limit: 5, offset: 10 })
    ).resolves.toEqual({
      records: [{ run_id: "run-1", goal: "Inspect release", state: "completed" }],
      total: 1,
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/hca/runs?q=release&limit=5&offset=10",
      undefined
    );
  });

  test("decideRunApproval posts to the canonical approval route and validates the summary", async () => {
    const { decideRunApproval } = loadApiModule();

    global.fetch.mockResolvedValue(
      createJsonResponse({
        run_id: "run-approve",
        goal: "Please remember this note",
        state: "completed",
        approval_id: "approval-1",
        last_approval_decision: "granted",
      })
    );

    await expect(
      decideRunApproval("run-approve", "approve", "approval-1")
    ).resolves.toMatchObject({
      run_id: "run-approve",
      state: "completed",
      approval_id: "approval-1",
      last_approval_decision: "granted",
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/hca/run/run-approve/approve",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_id: "approval-1" }),
      })
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
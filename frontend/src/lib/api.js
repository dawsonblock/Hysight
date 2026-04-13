const configuredBackendUrl = process.env.REACT_APP_BACKEND_URL?.trim();
const normalizedBackendUrl = configuredBackendUrl
  ? configuredBackendUrl.replace(/\/+$/, "")
  : "";

export const API_BASE_URL = normalizedBackendUrl
  ? `${normalizedBackendUrl}/api`
  : "/api";

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

export async function fetchJson(path, init) {
  const response = await apiFetch(path, init);
  const payload = await readResponseBody(response);

  if (!response.ok) {
    throw new Error(formatErrorMessage(response, payload));
  }

  return payload;
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
    }
  );
}

export function listRuns({ query, limit, offset }) {
  return fetchJson(
    `/hca/runs${buildQuery({
      q: typeof query === "string" ? query.trim() : undefined,
      limit,
      offset,
    })}`
  );
}

export function getRunSummary(runId) {
  return fetchJson(`/hca/run/${encodeSegment(runId)}`);
}

export function listRunEvents(runId, { limit, offset } = {}) {
  return fetchJson(
    `/hca/run/${encodeSegment(runId)}/events${buildQuery({
      limit,
      offset,
    })}`
  );
}

export function listRunArtifacts(runId, { limit, offset } = {}) {
  return fetchJson(
    `/hca/run/${encodeSegment(runId)}/artifacts${buildQuery({
      limit,
      offset,
    })}`
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
    )}${buildQuery({ preview_bytes: previewBytes })}`
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
    })}`
  );
}

export function deleteMemoryRecord(memoryId) {
  return fetchJson(`/hca/memory/${encodeSegment(memoryId)}`, {
    method: "DELETE",
  });
}
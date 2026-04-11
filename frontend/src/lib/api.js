const configuredBackendUrl = process.env.REACT_APP_BACKEND_URL?.trim();
const normalizedBackendUrl = configuredBackendUrl
  ? configuredBackendUrl.replace(/\/+$/, "")
  : "";

export const API_BASE_URL = normalizedBackendUrl
  ? `${normalizedBackendUrl}/api`
  : "/api";

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
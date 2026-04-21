import { useEffect, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api";
import { getAutonomyWorkspace } from "@/lib/autonomy-api";

const POLL_INTERVAL_MS = 15000;
const STALE_SYNC_THRESHOLD_MS = POLL_INTERVAL_MS * 2;

const EMPTY_ERRORS = {
  status: "",
  agents: "",
  schedules: "",
  inbox: "",
  runs: "",
  checkpoints: "",
  budgets: "",
  escalations: "",
};

const EMPTY_DATA = {
  status: null,
  agents: [],
  schedules: [],
  inbox: [],
  runs: [],
  checkpoints: [],
  budgets: [],
  escalations: [],
};

export default function useAutonomyPolling() {
  const loadCancelledRef = useRef(false);
  const requestStateRef = useRef({
    inFlight: false,
    queued: false,
    queuedIsPolling: true,
  });
  const requestWorkspaceLoadRef = useRef(null);
  const hasLoadedOnceRef = useRef(false);

  const [resourceData, setResourceData] = useState(EMPTY_DATA);
  const [resourceErrors, setResourceErrors] = useState(EMPTY_ERRORS);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastAttemptedSyncAt, setLastAttemptedSyncAt] = useState(null);
  const [lastSuccessfulSyncAt, setLastSuccessfulSyncAt] = useState(null);

  async function loadWorkspaceOnce(isPolling = false) {
    const attemptStartedAt = new Date().toISOString();
    setLastAttemptedSyncAt(attemptStartedAt);

    if (!hasLoadedOnceRef.current && !isPolling) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }

    const nextErrors = { ...EMPTY_ERRORS };
    const nextValues = {};
    let successfulResourceCount = 0;

    try {
      const snapshot = await getAutonomyWorkspace();

      if (loadCancelledRef.current) {
        return;
      }

      const sectionErrors = snapshot.section_errors || {};

      nextValues.status = snapshot.status ?? null;
      nextValues.agents = snapshot.agents || [];
      nextValues.schedules = snapshot.schedules || [];
      nextValues.inbox = snapshot.inbox || [];
      nextValues.runs = snapshot.runs || [];
      nextValues.checkpoints = snapshot.checkpoints || [];
      nextValues.budgets = snapshot.budgets || [];
      nextValues.escalations = snapshot.escalations || [];

      for (const key of Object.keys(EMPTY_ERRORS)) {
        nextErrors[key] = sectionErrors[key] || "";
      }

      successfulResourceCount = Object.values(nextErrors).filter(
        (msg) => msg === ""
      ).length;
    } catch (err) {
      if (loadCancelledRef.current) {
        return;
      }
      const msg = toErrorMessage(err, "Unable to load workspace.");
      for (const key of Object.keys(EMPTY_ERRORS)) {
        nextErrors[key] = msg;
      }
    }

    const completedAt = new Date().toISOString();

    setResourceData((currentValue) => ({
      ...currentValue,
      ...nextValues,
    }));
    setResourceErrors(nextErrors);
    hasLoadedOnceRef.current = true;
    setLoading(false);
    setRefreshing(false);

    if (successfulResourceCount > 0) {
      setLastSuccessfulSyncAt(completedAt);
    }
  }

  async function requestWorkspaceLoad(isPolling = false) {
    if (loadCancelledRef.current) {
      return;
    }

    const requestState = requestStateRef.current;

    if (requestState.inFlight) {
      requestState.queued = true;
      requestState.queuedIsPolling = requestState.queuedIsPolling && isPolling;
      return;
    }

    requestState.inFlight = true;
    let nextIsPolling = isPolling;

    try {
      do {
        requestState.queued = false;
        requestState.queuedIsPolling = true;
        await loadWorkspaceOnce(nextIsPolling);
        nextIsPolling = requestState.queuedIsPolling;
      } while (requestState.queued && !loadCancelledRef.current);
    } finally {
      requestState.inFlight = false;
    }
  }

  requestWorkspaceLoadRef.current = requestWorkspaceLoad;

  useEffect(() => {
    const requestState = requestStateRef.current;

    loadCancelledRef.current = false;
    requestWorkspaceLoadRef.current?.(false);

    const intervalId = window.setInterval(() => {
      requestWorkspaceLoadRef.current?.(true);
    }, POLL_INTERVAL_MS);

    return () => {
      loadCancelledRef.current = true;
      requestState.inFlight = false;
      requestState.queued = false;
      requestState.queuedIsPolling = true;
      window.clearInterval(intervalId);
    };
  }, []);

  const degradedResourceKeys = Object.entries(resourceErrors)
    .filter(([, message]) => Boolean(message))
    .map(([resourceKey]) => resourceKey);

  const isStaleData =
    Boolean(lastAttemptedSyncAt && lastSuccessfulSyncAt) &&
    new Date(lastAttemptedSyncAt).getTime() -
      new Date(lastSuccessfulSyncAt).getTime() >=
      STALE_SYNC_THRESHOLD_MS;

  return {
    resourceData,
    resourceErrors,
    loading,
    refreshing,
    degradedResourceKeys,
    isStaleData,
    lastAttemptedSyncAt,
    lastSuccessfulSyncAt,
    refreshWorkspace: () => requestWorkspaceLoadRef.current?.(false),
  };
}

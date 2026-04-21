import { useEffect, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api";
import {
  getAutonomyStatus,
  listAutonomyAgents,
  listAutonomyBudgets,
  listAutonomyCheckpoints,
  listAutonomyEscalations,
  listAutonomyInbox,
  listAutonomyRuns,
  listAutonomySchedules,
} from "@/lib/autonomy-api";

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

const LOADER_ENTRIES = [
  ["status", getAutonomyStatus],
  ["agents", listAutonomyAgents],
  ["schedules", listAutonomySchedules],
  ["inbox", () => listAutonomyInbox()],
  ["runs", listAutonomyRuns],
  ["checkpoints", () => listAutonomyCheckpoints()],
  ["budgets", listAutonomyBudgets],
  ["escalations", listAutonomyEscalations],
];

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

    const settledResources = await Promise.allSettled(
      LOADER_ENTRIES.map(([, loader]) => Promise.resolve().then(() => loader()))
    );

    if (loadCancelledRef.current) {
      return;
    }

    const nextErrors = { ...EMPTY_ERRORS };
    const nextValues = {};
    let successfulResourceCount = 0;

    LOADER_ENTRIES.forEach(([resourceKey], index) => {
      const result = settledResources[index];

      if (result.status === "fulfilled") {
        successfulResourceCount += 1;
        if (resourceKey === "status") {
          nextValues.status = result.value;
        } else if (resourceKey === "agents") {
          nextValues.agents = result.value.agents || [];
        } else if (resourceKey === "schedules") {
          nextValues.schedules = result.value.schedules || [];
        } else if (resourceKey === "inbox") {
          nextValues.inbox = result.value.items || [];
        } else if (resourceKey === "runs") {
          nextValues.runs = result.value.runs || [];
        } else if (resourceKey === "checkpoints") {
          nextValues.checkpoints = result.value.checkpoints || [];
        } else if (resourceKey === "budgets") {
          nextValues.budgets = result.value.ledgers || [];
        } else if (resourceKey === "escalations") {
          nextValues.escalations = result.value.escalations || [];
        }
      } else {
        nextErrors[resourceKey] = toErrorMessage(
          result.reason,
          `Unable to load ${resourceKey}.`
        );
      }
    });

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

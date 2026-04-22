import { useEffect, useRef, useState } from "react";
import { getRunSummary, toErrorMessage } from "@/lib/api";

export default function useAutonomyRunSummaries({ selectedRunId, activeRunIds = [] }) {
  const [runSummaries, setRunSummaries] = useState({});
  const [runSummariesError, setRunSummariesError] = useState("");
  const activeRunIdsRef = useRef(activeRunIds);

  const activeRunIdsKey = activeRunIds.slice().sort().join(",");

  useEffect(() => {
    activeRunIdsRef.current = activeRunIds;

    if (activeRunIds.length === 0) {
      setRunSummaries({});
      setRunSummariesError("");
      return;
    }

    let cancelled = false;

    Promise.all(
      activeRunIds.map((runId) =>
        getRunSummary(runId)
          .then((summary) => ({ runId, summary, error: null }))
          .catch((err) => ({ runId, summary: null, error: err }))
      )
    ).then((results) => {
      if (cancelled) return;

      const nextSummaries = {};
      let firstError = null;
      for (const { runId, summary, error } of results) {
        if (summary !== null) {
          nextSummaries[runId] = summary;
        }
        if (error !== null && firstError === null) {
          firstError = error;
        }
      }

      setRunSummaries(nextSummaries);
      setRunSummariesError(firstError ? toErrorMessage(firstError, "Failed to load run summaries.") : "");
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRunIdsKey]);

  const selectedRunSummary = selectedRunId ? (runSummaries[selectedRunId] ?? null) : null;

  return { selectedRunSummary, runSummaries, runSummariesError };
}

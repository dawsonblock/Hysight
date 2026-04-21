import { useEffect, useState } from "react";
import { getRunSummary } from "@/lib/api";

export default function useAutonomyRunSummaries({ selectedRunId }) {
  const [selectedRunSummary, setSelectedRunSummary] = useState(null);

  useEffect(() => {
    if (!selectedRunId) {
      setSelectedRunSummary(null);
      return;
    }

    let cancelled = false;

    getRunSummary(selectedRunId).then((summary) => {
      if (!cancelled) {
        setSelectedRunSummary(summary);
      }
    }).catch(() => {
      if (!cancelled) {
        setSelectedRunSummary(null);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [selectedRunId]);

  return { selectedRunSummary };
}

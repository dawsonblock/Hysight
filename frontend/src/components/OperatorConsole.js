import { useEffect, useState } from "react";
import "./OperatorConsole.css";
import {
  decideRunApproval,
  getRunArtifactDetail,
  getSubsystems,
  getRunSummary,
  listRunArtifacts,
  listRunEvents,
  listRuns,
  toErrorMessage,
} from "@/lib/api";
import { toast } from "@/hooks/use-toast";
import { summarizeApprovalToast } from "@/lib/run-presentation";

const RUN_PAGE_SIZE = 10;
const RUN_FETCH_LIMIT = 100;
const EVENT_LIMIT = 80;
const ARTIFACT_LIMIT = 50;
const FILTER_ALL = "all";

const RUN_STATE_FILTERS = [
  { value: FILTER_ALL, label: "All" },
  { value: "awaiting_approval", label: "Approval" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "halted", label: "Halted" },
];

const STORAGE_KEYS = {
  operatorTab: "hysight:operator-tab",
  runQuery: "hysight:run-query",
  runStateFilter: "hysight:run-state-filter",
  runStrategyFilter: "hysight:run-strategy-filter",
};

const STATE_META = {
  completed: { color: "#0f766e", bg: "#ccfbf1", border: "#99f6e4" },
  awaiting_approval: {
    color: "#7c3aed",
    bg: "#f3e8ff",
    border: "#d8b4fe",
  },
  failed: { color: "#b91c1c", bg: "#fee2e2", border: "#fca5a5" },
  halted: { color: "#b45309", bg: "#fef3c7", border: "#fcd34d" },
};

const DEFAULT_STATE_META = {
  color: "#334155",
  bg: "#e2e8f0",
  border: "#cbd5e1",
};

const TABS = ["overview", "events", "artifacts"];

const STRATEGY_LABELS = {
  single_action_dispatch: "Direct dispatch",
  memory_persistence_strategy: "Memory write",
  information_retrieval_strategy: "Memory retrieval",
  artifact_authoring_strategy: "Artifact authoring",
};

function readStoredValue(key, fallback) {
  try {
    const storedValue = window.localStorage.getItem(key);
    return storedValue ?? fallback;
  } catch {
    return fallback;
  }
}

export default function OperatorConsole({
  selectedRunId,
  onSelectRun,
  refreshToken,
  onRunObserved,
}) {
  const [runs, setRuns] = useState([]);
  const [totalRuns, setTotalRuns] = useState(0);
  const [runQuery, setRunQuery] = useState(() =>
    readStoredValue(STORAGE_KEYS.runQuery, "")
  );
  const [runPage, setRunPage] = useState(0);
  const [runStateFilter, setRunStateFilter] = useState(() =>
    readStoredValue(STORAGE_KEYS.runStateFilter, FILTER_ALL)
  );
  const [runStrategyFilter, setRunStrategyFilter] = useState(() =>
    readStoredValue(STORAGE_KEYS.runStrategyFilter, FILTER_ALL)
  );
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState("");
  const [subsystems, setSubsystems] = useState(null);
  const [subsystemsLoading, setSubsystemsLoading] = useState(false);
  const [subsystemsError, setSubsystemsError] = useState("");

  const [runDetail, setRunDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

  const [events, setEvents] = useState([]);
  const [eventTotal, setEventTotal] = useState(0);
  const [artifacts, setArtifacts] = useState([]);
  const [artifactTotal, setArtifactTotal] = useState(0);

  const [selectedArtifactId, setSelectedArtifactId] = useState(null);
  const [artifactDetail, setArtifactDetail] = useState(null);
  const [artifactLoading, setArtifactLoading] = useState(false);
  const [artifactError, setArtifactError] = useState("");
  const [localRefreshToken, setLocalRefreshToken] = useState(0);
  const [approvalPendingDecision, setApprovalPendingDecision] = useState(null);
  const [approvalError, setApprovalError] = useState("");
  const [activeTab, setActiveTab] = useState(() => {
    const storedTab = readStoredValue(STORAGE_KEYS.operatorTab, "overview");
    return TABS.includes(storedTab) ? storedTab : "overview";
  });

  useEffect(() => {
    let cancelled = false;

    async function loadRuns() {
      setRunsLoading(true);
      setRunsError("");

      try {
        const data = await listRuns({
          query: runQuery,
          limit: RUN_FETCH_LIMIT,
          offset: 0,
        });
        if (!cancelled) {
          setRuns(Array.isArray(data?.records) ? data.records : []);
          setTotalRuns(typeof data?.total === "number" ? data.total : 0);
        }
      } catch (error) {
        if (!cancelled) {
          setRuns([]);
          setTotalRuns(0);
          setRunsError(toErrorMessage(error, "Unable to load runs."));
        }
      } finally {
        if (!cancelled) {
          setRunsLoading(false);
        }
      }
    }

    loadRuns();
    return () => {
      cancelled = true;
    };
  }, [localRefreshToken, refreshToken, runQuery]);

  useEffect(() => {
    let cancelled = false;

    async function loadSubsystems() {
      setSubsystemsLoading(true);
      setSubsystemsError("");

      try {
        const data = await getSubsystems();

        if (!cancelled) {
          setSubsystems(data);
        }
      } catch (error) {
        if (!cancelled) {
          setSubsystems(null);
          setSubsystemsError(
            toErrorMessage(error, "Unable to load subsystem health.")
          );
        }
      } finally {
        if (!cancelled) {
          setSubsystemsLoading(false);
        }
      }
    }

    loadSubsystems();
    return () => {
      cancelled = true;
    };
  }, [localRefreshToken, refreshToken]);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEYS.runQuery, runQuery);
      window.localStorage.setItem(
        STORAGE_KEYS.runStateFilter,
        runStateFilter
      );
      window.localStorage.setItem(
        STORAGE_KEYS.runStrategyFilter,
        runStrategyFilter
      );
      window.localStorage.setItem(STORAGE_KEYS.operatorTab, activeTab);
    } catch {
      // Ignore storage failures and keep the console interactive.
    }
  }, [activeTab, runQuery, runStateFilter, runStrategyFilter]);

  const availableStrategies = Array.from(
    new Set(runs.map((run) => run.plan?.strategy).filter(Boolean))
  );
  const filteredRuns = runs.filter((run) => {
    if (runStateFilter !== FILTER_ALL && run.state !== runStateFilter) {
      return false;
    }

    if (
      runStrategyFilter !== FILTER_ALL &&
      (run.plan?.strategy || "") !== runStrategyFilter
    ) {
      return false;
    }

    return true;
  });
  const maxRunPage = Math.max(
    0,
    Math.ceil(filteredRuns.length / RUN_PAGE_SIZE) - 1
  );
  const visibleRuns = filteredRuns.slice(
    runPage * RUN_PAGE_SIZE,
    runPage * RUN_PAGE_SIZE + RUN_PAGE_SIZE
  );
  const selectedRunHidden =
    Boolean(selectedRunId) &&
    filteredRuns.every((run) => run.run_id !== selectedRunId);
  const hasRunFilters =
    runQuery.trim().length > 0 ||
    runStateFilter !== FILTER_ALL ||
    runStrategyFilter !== FILTER_ALL;
  const selectedRunRecord =
    runs.find((run) => run.run_id === selectedRunId) || null;
  const selectedRunSnapshot = runDetail || selectedRunRecord;
  const runStateSummary = summarizeRunPortfolio(filteredRuns);

  useEffect(() => {
    if (runPage > maxRunPage) {
      setRunPage(maxRunPage);
    }
  }, [maxRunPage, runPage]);

  useEffect(() => {
    setApprovalPendingDecision(null);
    setApprovalError("");
  }, [selectedRunId]);

  useEffect(() => {
    if (!selectedRunId && filteredRuns.length > 0) {
      onSelectRun?.(filteredRuns[0].run_id);
    }
  }, [filteredRuns, onSelectRun, selectedRunId]);

  useEffect(() => {
    let cancelled = false;

    async function loadRunSurface() {
      if (!selectedRunId) {
        setRunDetail(null);
        setEvents([]);
        setEventTotal(0);
        setArtifacts([]);
        setArtifactTotal(0);
        return;
      }

      setDetailLoading(true);
      setDetailError("");
      setSelectedArtifactId(null);
      setArtifactDetail(null);
      setArtifactError("");

      try {
        const [detail, eventData, artifactData] = await Promise.all([
          getRunSummary(selectedRunId),
          listRunEvents(selectedRunId, { limit: EVENT_LIMIT }),
          listRunArtifacts(selectedRunId, { limit: ARTIFACT_LIMIT }),
        ]);

        if (cancelled) {
          return;
        }

        setRunDetail(detail);
        setEvents(Array.isArray(eventData?.records) ? eventData.records : []);
        setEventTotal(
          typeof eventData?.total === "number" ? eventData.total : 0
        );
        setArtifacts(
          Array.isArray(artifactData?.records) ? artifactData.records : []
        );
        setArtifactTotal(
          typeof artifactData?.total === "number" ? artifactData.total : 0
        );
      } catch (error) {
        if (!cancelled) {
          setRunDetail(null);
          setEvents([]);
          setArtifacts([]);
          setDetailError(toErrorMessage(error, "Unable to load run details."));
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    }

    loadRunSurface();
    return () => {
      cancelled = true;
    };
  }, [localRefreshToken, refreshToken, selectedRunId]);

  useEffect(() => {
    let cancelled = false;

    async function loadArtifactDetail() {
      if (!selectedRunId || !selectedArtifactId) {
        setArtifactDetail(null);
        return;
      }

      setArtifactLoading(true);
      setArtifactError("");
      try {
        const data = await getRunArtifactDetail(
          selectedRunId,
          selectedArtifactId
        );
        if (!cancelled) {
          setArtifactDetail(data);
        }
      } catch (error) {
        if (!cancelled) {
          setArtifactDetail(null);
          setArtifactError(
            toErrorMessage(error, "Unable to load artifact content.")
          );
        }
      } finally {
        if (!cancelled) {
          setArtifactLoading(false);
        }
      }
    }

    loadArtifactDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedArtifactId, selectedRunId]);

  const clearRunFilters = () => {
    setRunQuery("");
    setRunStateFilter(FILTER_ALL);
    setRunStrategyFilter(FILTER_ALL);
    setRunPage(0);
  };

  const handleApprovalDecision = async (decision) => {
    if (!selectedRunId || !selectedRunSnapshot?.approval_id) {
      return;
    }

    setApprovalPendingDecision(decision);
    setApprovalError("");

    try {
      const data = await decideRunApproval(
        selectedRunId,
        decision,
        selectedRunSnapshot.approval_id
      );

      toast({
        title: decision === "approve" ? "Approval granted" : "Approval denied",
        description: summarizeApprovalToast(data, decision),
        variant: data?.state === "failed" ? "destructive" : "default",
      });

      setRunDetail(data);
      setSelectedArtifactId(null);
      setArtifactDetail(null);
      setArtifactError("");
      setDetailError("");
      setApprovalPendingDecision(null);
      setLocalRefreshToken((currentValue) => currentValue + 1);
      onRunObserved?.(data?.run_id || selectedRunId);
    } catch (error) {
      const message = toErrorMessage(
        error,
        decision === "approve" ? "Approval failed." : "Deny failed."
      );

      toast({
        title: decision === "approve" ? "Approval failed" : "Deny failed",
        description: message,
        variant: "destructive",
      });

      setApprovalPendingDecision(null);
      setApprovalError(message);
    }
  };

  return (
    <aside className="runs-console">
      <div className="runs-consoleHeader">
        <div>
          <div style={S.eyebrow}>Runs</div>
          <div style={S.title}>Runs workspace</div>
          <div style={S.subtitle}>
            Replay-backed answers, approvals, and stored evidence.
          </div>
        </div>
        <button
          className="runs-consoleAction"
          onClick={() => {
            if (hasRunFilters) {
              clearRunFilters();
              return;
            }

            if (filteredRuns.length > 0) {
              onSelectRun?.(filteredRuns[0].run_id);
            }
          }}
          style={S.refreshBtn}
          type="button"
        >
          {hasRunFilters ? "Clear filters" : "Latest run"}
        </button>
      </div>

      <MetricStrip
        items={[
          {
            label: "Visible runs",
            value: filteredRuns.length,
            hint:
              totalRuns > runs.length
                ? `latest ${runs.length} loaded`
                : "full local window",
          },
          {
            label: "Needs sign-off",
            value: runStateSummary.awaiting_approval,
            hint:
              runStateSummary.awaiting_approval > 0
                ? "operator action pending"
                : "no pending approvals",
            tone: "attention",
          },
          {
            label: "Closed loop",
            value: runStateSummary.completed,
            hint:
              runStateSummary.completed > 0
                ? "completed replay surfaces"
                : "none completed yet",
            tone: "success",
          },
          {
            label: "Exceptions",
            value: runStateSummary.failed + runStateSummary.halted,
            hint:
              runStateSummary.failed + runStateSummary.halted > 0
                ? "failed or operator-stopped"
                : "healthy recent window",
            tone:
              runStateSummary.failed + runStateSummary.halted > 0
                ? "danger"
                : "default",
          },
        ]}
      />

      <SubsystemStatusStrip
        subsystems={subsystems}
        loading={subsystemsLoading}
        error={subsystemsError}
      />

      <FocusedRunCard
        run={selectedRunSnapshot}
        loading={detailLoading}
        pendingDecision={approvalPendingDecision}
        approvalError={approvalError}
        onApprove={() => handleApprovalDecision("approve")}
        onDeny={() => handleApprovalDecision("deny")}
      />

      <div className="runs-consoleSearch">
        <input
          value={runQuery}
          onChange={(event) => {
            setRunQuery(event.target.value);
            setRunPage(0);
          }}
          aria-label="Search runs"
          placeholder="Search runs by goal, id, or strategy"
          style={S.searchInput}
        />
        {runQuery && (
          <button
            className="runs-consoleAction runs-consoleAction--secondary"
            type="button"
            onClick={() => {
              setRunQuery("");
              setRunPage(0);
            }}
          >
            Clear
          </button>
        )}
      </div>

      <div className="runs-consoleSectionHeader" style={S.runListHeader}>
        <span style={S.sectionLabel}>Runs</span>
        <span style={S.sectionCount}>
          {filteredRuns.length} shown
          {totalRuns > runs.length ? ` • latest ${runs.length} of ${totalRuns}` : ` • ${totalRuns} total`}
        </span>
      </div>

      <div className="runs-consoleFilters">
        <div style={S.filterChipRow}>
          {RUN_STATE_FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              aria-pressed={runStateFilter === filter.value}
              onClick={() => {
                setRunStateFilter(filter.value);
                setRunPage(0);
              }}
              style={{
                ...S.filterChip,
                ...(runStateFilter === filter.value ? S.filterChipActive : null),
              }}
            >
              {filter.label}
            </button>
          ))}
        </div>

        {availableStrategies.length > 0 && (
          <div style={S.filterChipRow}>
            <button
              type="button"
              aria-pressed={runStrategyFilter === FILTER_ALL}
              onClick={() => {
                setRunStrategyFilter(FILTER_ALL);
                setRunPage(0);
              }}
              style={{
                ...S.filterChip,
                ...(runStrategyFilter === FILTER_ALL ? S.filterChipActive : null),
              }}
            >
              All strategies
            </button>
            {availableStrategies.map((strategy) => (
              <button
                key={strategy}
                type="button"
                aria-pressed={runStrategyFilter === strategy}
                onClick={() => {
                  setRunStrategyFilter(strategy);
                  setRunPage(0);
                }}
                style={{
                  ...S.filterChip,
                  ...(runStrategyFilter === strategy ? S.filterChipActive : null),
                }}
              >
                {formatStrategyLabel(strategy)}
              </button>
            ))}
          </div>
        )}

        {selectedRunHidden && (
          <div className="runs-consoleNotice" style={S.noticeBar}>
            The current selection is outside the active run filters.
          </div>
        )}
      </div>

      <div className="runs-consoleList">
        {runsLoading && <PanelMessage text="Loading runs…" />}
        {!runsLoading && runsError && <PanelMessage text={runsError} tone="error" />}
        {!runsLoading && !runsError && filteredRuns.length === 0 && (
          <PanelMessage text="No runs found." />
        )}
        {visibleRuns.map((run) => (
          <RunRow
            key={run.run_id}
            run={run}
            selected={run.run_id === selectedRunId}
            onClick={() => onSelectRun?.(run.run_id)}
          />
        ))}
      </div>

      {filteredRuns.length > RUN_PAGE_SIZE && (
        <div className="runs-consolePagination" style={S.pagination}>
          <button
            type="button"
            style={{ ...S.pageBtn, opacity: runPage === 0 ? 0.4 : 1 }}
            disabled={runPage === 0}
            onClick={() => setRunPage((currentValue) => currentValue - 1)}
          >
            Prev
          </button>
          <span style={S.pageInfo}>
            {runPage * RUN_PAGE_SIZE + 1}-{Math.min(
              (runPage + 1) * RUN_PAGE_SIZE,
              filteredRuns.length
            )}
          </span>
          <button
            type="button"
            style={{
              ...S.pageBtn,
              opacity:
                (runPage + 1) * RUN_PAGE_SIZE >= filteredRuns.length ? 0.4 : 1,
            }}
            disabled={(runPage + 1) * RUN_PAGE_SIZE >= filteredRuns.length}
            onClick={() => setRunPage((currentValue) => currentValue + 1)}
          >
            Next
          </button>
        </div>
      )}

      <div className="runs-consoleDetail">
        <div style={S.tabs}>
          {TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              style={{
                ...S.tab,
                ...(activeTab === tab ? S.tabActive : null),
              }}
            >
              {formatTabLabel(
                tab,
                tab === "events"
                  ? eventTotal || events.length
                  : tab === "artifacts"
                    ? artifactTotal || artifacts.length
                    : null
              )}
            </button>
          ))}
        </div>

        {detailLoading && <PanelMessage text="Loading run surface…" />}
        {!detailLoading && detailError && (
          <PanelMessage text={detailError} tone="error" />
        )}
        {!detailLoading && !detailError && !runDetail && (
          <PanelMessage text="Select a run to inspect its replay-backed state." />
        )}

        {!detailLoading && !detailError && runDetail && activeTab === "overview" && (
          <OverviewPanel run={runDetail} />
        )}
        {!detailLoading && !detailError && runDetail && activeTab === "events" && (
          <EventsPanel events={events} total={eventTotal} />
        )}
        {!detailLoading && !detailError && runDetail && activeTab === "artifacts" && (
          <ArtifactsPanel
            artifacts={artifacts}
            artifactDetail={artifactDetail}
            artifactError={artifactError}
            artifactLoading={artifactLoading}
            selectedArtifactId={selectedArtifactId}
            total={artifactTotal}
            onSelectArtifact={setSelectedArtifactId}
          />
        )}
      </div>
    </aside>
  );
}

function RunRow({ run, selected, onClick }) {
  const meta = STATE_META[run.state] || DEFAULT_STATE_META;
  return (
    <button
      className={`runs-runRow${selected ? " is-selected" : ""}`}
      type="button"
      onClick={onClick}
    >
      <div style={S.runRowTop}>
        <span
          style={{
            ...S.runBadge,
            color: meta.color,
            background: meta.bg,
            borderColor: meta.border,
          }}
        >
          {formatStateLabel(run.state)}
        </span>
        <span style={S.runTime}>{formatDateTime(run.updated_at)}</span>
      </div>
      <div style={S.runGoal}>{run.goal}</div>
      <div style={S.runMeta}>
        <span>{formatStrategyLabel(run.plan?.strategy) || "No strategy"}</span>
        <span>{run.event_count} events</span>
        <span>{run.artifacts_count} artifacts</span>
      </div>
    </button>
  );
}

function FocusedRunCard({
  run,
  loading,
  pendingDecision,
  approvalError,
  onApprove,
  onDeny,
}) {
  if (!run && !loading) {
    return null;
  }

  const signal = summarizeRunSignal(run);
  const canResolveApproval = isApprovalActionable(run);
  const { request, binding } = getApprovalContext(run);
  const approvalTokens = approvalBindingTokens(binding);

  return (
    <section className={`runs-focusCard runs-focusCard--${signal.tone}`}>
      <div style={S.focusHeader}>
        <div>
          <div style={S.focusEyebrow}>Focused run</div>
          <div style={S.focusTitle}>{run?.goal || "Loading replay surface…"}</div>
          <div style={S.focusSubtitle}>{signal.summary}</div>
        </div>
        <span
          style={{
            ...S.focusBadge,
            color: signal.badge.color,
            background: signal.badge.bg,
            borderColor: signal.badge.border,
          }}
        >
          {signal.label}
        </span>
      </div>

      <MetricStrip
        compact
        items={[
          {
            label: "Run",
            value: shortenIdentifier(run?.run_id),
            hint: run?.run_id,
            mono: true,
          },
          {
            label: "Action",
            value: run?.action_taken?.kind || run?.plan?.action || "—",
            hint: formatStrategyLabel(run?.plan?.strategy) || "No strategy",
          },
          {
            label: "Approval",
            value: formatApprovalStatus(run),
            hint: hasValue(run?.approval_id) ? "approval binding active" : "no approval bound",
            mono: hasValue(run?.approval_id),
          },
          {
            label: "Duration",
            value: formatDuration(run?.metrics?.run_duration_ms),
            hint: `${run?.event_count ?? 0} events • ${run?.artifacts_count ?? 0} artifacts`,
          },
        ]}
      />

      {canResolveApproval && (
        <div style={S.focusActionCard}>
          <div style={S.focusActionHeader}>
            <div>
              <div style={S.focusActionEyebrow}>Operator action required</div>
              <div style={S.focusActionTitle}>
                {run.action_taken?.kind || run.plan?.action || "Action"} is waiting for sign-off.
              </div>
            </div>
            <span style={S.focusActionId}>{shortenIdentifier(run.approval_id)}</span>
          </div>

          {hasValue(request?.reason) && (
            <div style={S.focusActionContext}>{request.reason}</div>
          )}

          {approvalTokens.length > 0 && <TokenList values={approvalTokens} mono />}

          {hasValue(binding?.policy_snapshot) && (
            <section style={S.section}>
              <div style={S.sectionLabel}>Policy snapshot</div>
              <pre style={S.focusActionPayload}>
                {formatPayload(binding.policy_snapshot)}
              </pre>
            </section>
          )}

          {hasValue(run.action_taken?.arguments) && (
            <section style={S.section}>
              <div style={S.sectionLabel}>Pending arguments</div>
              <pre style={S.focusActionPayload}>
                {formatPayload(run.action_taken.arguments)}
              </pre>
            </section>
          )}

          <div style={S.focusActionButtons}>
            <button
              data-testid="operator-approve-btn"
              type="button"
              onClick={onApprove}
              disabled={pendingDecision !== null}
              style={{
                ...S.focusApproveBtn,
                opacity: pendingDecision !== null ? 0.7 : 1,
              }}
            >
              {pendingDecision === "approve" ? "Approving..." : "Approve"}
            </button>
            <button
              data-testid="operator-deny-btn"
              type="button"
              onClick={onDeny}
              disabled={pendingDecision !== null}
              style={{
                ...S.focusDenyBtn,
                opacity: pendingDecision !== null ? 0.7 : 1,
              }}
            >
              {pendingDecision === "deny" ? "Denying..." : "Deny"}
            </button>
          </div>

          {approvalError && <div style={S.focusActionError}>{approvalError}</div>}
        </div>
      )}
    </section>
  );
}

function OverviewPanel({ run }) {
  const plan = run.plan || {};
  const perception = run.perception || {};
  const critique = run.critique || {};
  const actionTaken = run.action_taken || {};
  const actionResult = run.action_result || {};
  const activeWorkflow = run.active_workflow || {};
  const { approval, request, decision, grant, consumption, binding } =
    getApprovalContext(run);
  const workflowBudget = run.workflow_budget || {};
  const workflowCheckpoint = run.workflow_checkpoint || {};
  const workflowOutcome = run.workflow_outcome || {};
  const memoryHits = Array.isArray(run.memory_hits) ? run.memory_hits : [];
  const workflowSteps = Array.isArray(run.workflow_step_history)
    ? run.workflow_step_history
    : [];
  const workflowArtifacts = Array.isArray(run.workflow_artifacts)
    ? run.workflow_artifacts
    : [];
  const memoryCountItems = Object.entries(run.memory_counts || {}).map(
    ([key, value]) => ({
      label: formatSnakeLabel(key),
      value: String(value),
    })
  );
  const memoryOutcomeItems = Object.entries(run.memory_outcomes || {}).map(
    ([key, value]) => ({
      label: formatSnakeLabel(key),
      value: summarizeValue(value),
    })
  );
  const overviewFacts = [
    { label: "State", value: formatStateLabel(run.state) },
    { label: "Action", value: actionTaken.kind || plan.action || "—" },
    { label: "Approval", value: formatApprovalStatus(run) },
    { label: "Latest receipt", value: run.latest_receipt?.status || actionResult.status || "—" },
    { label: "Workflow", value: activeWorkflow.workflow_class || "—" },
    { label: "Events", value: String(run.event_count ?? 0) },
    { label: "Artifacts", value: String(run.artifacts_count ?? 0) },
    {
      label: "Duration",
      value: formatDuration(run.metrics?.run_duration_ms),
    },
  ];
  const needsReview =
    isApprovalActionable(run) ||
    hasValue(run.approval_id) ||
    hasValue(approval);
  const reviewTokens = approvalBindingTokens(binding);

  return (
    <div className="runs-detailBody">
      <ReplayDigestCard run={run} />

      <section className="runs-overviewLead">
        <div className="runs-overviewEyebrow">What happened</div>
        <h3 className="runs-overviewTitle">{summarizeOverviewHeadline(run)}</h3>
        <p className="runs-overviewDescription">
          {summarizeOverviewDescription(run)}
        </p>
        <div className="runs-overviewGrid">
          {overviewFacts.map((item) => (
            <SummaryField key={item.label} label={item.label} value={item.value} />
          ))}
        </div>
      </section>

      {needsReview && (
        <section className="runs-reviewCard">
          <div className="runs-overviewEyebrow">Needs review</div>
          <div className="runs-reviewTitle">
            {request?.action_kind || actionTaken.kind || plan.action || "Action"}
            {isApprovalActionable(run)
              ? " is waiting for operator approval."
              : " has recorded approval history."}
          </div>
          <p className="runs-reviewDescription">
            {request?.reason ||
              decision?.reason ||
              "Inspect the approval binding and arguments before moving on."}
          </p>
          {reviewTokens.length > 0 && <TokenList values={reviewTokens} mono />}
          {hasValue(actionTaken.arguments) && (
            <pre style={S.payloadPreview}>{formatPayload(actionTaken.arguments)}</pre>
          )}
        </section>
      )}

      <OverviewDisclosure
        label="Reasoning and workflow"
        description="Planning, perception, critique, workflow, and runtime details."
      >
        <FactSection
          label="Planning"
          items={[
            { label: "Strategy", value: plan.strategy },
            { label: "Suggested action", value: plan.action },
            { label: "Planning mode", value: plan.planning_mode },
            {
              label: "Confidence",
              value: formatConfidence(plan.confidence),
            },
            {
              label: "Memory context used",
              value: formatBoolean(plan.memory_context_used),
            },
            {
              label: "Memory retrieval",
              value: plan.memory_retrieval_status,
            },
            {
              label: "Memory retrieval error",
              value: plan.memory_retrieval_error,
            },
            { label: "Fallback reason", value: plan.fallback_reason },
            { label: "Rationale", value: plan.rationale },
          ]}
        />

        <FactSection
          label="Perception"
          items={[
            { label: "Intent class", value: perception.intent_class },
            { label: "Intent", value: perception.intent },
            { label: "Perception mode", value: perception.perception_mode },
            {
              label: "LLM attempted",
              value: formatBoolean(perception.llm_attempted),
            },
            {
              label: "Fallback reason",
              value: perception.fallback_reason,
            },
          ]}
        />

        <FactSection
          label="Critique"
          items={[
            { label: "Verdict", value: critique.verdict },
            { label: "Alignment", value: formatScore(critique.alignment) },
            {
              label: "Feasibility",
              value: formatScore(critique.feasibility),
            },
            { label: "Safety", value: formatScore(critique.safety) },
            {
              label: "Confidence delta",
              value: formatSignedNumber(critique.confidence_delta),
            },
            {
              label: "LLM powered",
              value: formatBoolean(critique.llm_powered),
            },
            {
              label: "Fallback reason",
              value: critique.fallback_reason,
            },
            {
              label: "Issues",
              value: Array.isArray(critique.issues)
                ? critique.issues.join(" • ")
                : "",
            },
            { label: "Rationale", value: critique.rationale },
          ]}
        />

        <FactSection
          label="Workflow"
          items={[
            { label: "Class", value: activeWorkflow.workflow_class },
            { label: "Strategy", value: activeWorkflow.strategy },
            { label: "Workflow id", value: activeWorkflow.workflow_id, mono: true },
            {
              label: "Budget",
              value: formatWorkflowBudget(workflowBudget),
            },
            {
              label: "Checkpoint",
              value: formatWorkflowCheckpoint(workflowCheckpoint),
              mono: true,
            },
            {
              label: "Outcome",
              value: formatWorkflowOutcome(workflowOutcome),
            },
            {
              label: "Workflow artifacts",
              value: String(workflowArtifacts.length || 0),
            },
          ]}
        />

        <FactSection
          label="Runtime"
          items={[
            { label: "Selected action", value: actionTaken.kind },
            {
              label: "Requires approval",
              value: formatBoolean(actionTaken.requires_approval),
            },
            {
              label: "Latest receipt",
              value: run.latest_receipt?.status || actionResult.status,
            },
            {
              label: "Execution error",
              value: actionResult.error,
            },
            {
              label: "Approval id",
              value: run.approval_id,
              mono: true,
            },
          ]}
        />

        {hasValue(actionTaken.arguments) && (
          <section style={S.section}>
            <div style={S.sectionLabel}>Action arguments</div>
            <pre style={S.payloadPreview}>{formatPayload(actionTaken.arguments)}</pre>
          </section>
        )}
      </OverviewDisclosure>

      {(hasValue(run.approval_id) ||
        hasValue(approval) ||
        hasValue(run.last_approval_decision)) && (
        <OverviewDisclosure
          label="Approval details"
          description="Binding, policy fingerprints, decision trail, and safeguards."
        >
          <FactSection
            label="Approval"
            items={[
              { label: "Status", value: formatApprovalStatus(run) },
              { label: "Approval id", value: run.approval_id, mono: true },
              { label: "Request reason", value: request?.reason },
              {
                label: "Requested action",
                value: request?.action_kind || actionTaken.kind || plan.action,
              },
              {
                label: "Action class",
                value: request?.action_class || binding?.action_class,
              },
              {
                label: "Requested at",
                value: request?.requested_at
                  ? formatDateTime(request.requested_at)
                  : "",
              },
              {
                label: "Decision",
                value: decision?.decision || run.last_approval_decision,
              },
              { label: "Decision actor", value: decision?.actor },
              { label: "Decision reason", value: decision?.reason },
              { label: "Granted by", value: grant?.actor },
              {
                label: "Granted at",
                value: grant?.granted_at ? formatDateTime(grant.granted_at) : "",
              },
              {
                label: "Consumed at",
                value: consumption?.consumed_at
                  ? formatDateTime(consumption.consumed_at)
                  : "",
              },
              { label: "Binding tool", value: binding?.tool_name, mono: true },
              { label: "Binding target", value: binding?.target, mono: true },
              {
                label: "Policy fingerprint",
                value: binding?.policy_fingerprint,
                mono: true,
              },
              {
                label: "Action fingerprint",
                value: binding?.action_fingerprint,
                mono: true,
              },
              {
                label: "Corruption count",
                value:
                  typeof approval?.corruption_count === "number"
                    ? String(approval.corruption_count)
                    : "",
              },
            ]}
          />

          {hasValue(binding?.policy_snapshot) && (
            <section style={S.section}>
              <div style={S.sectionLabel}>Approval policy snapshot</div>
              <pre style={S.payloadPreview}>
                {formatPayload(binding.policy_snapshot)}
              </pre>
            </section>
          )}
        </OverviewDisclosure>
      )}

      <OverviewDisclosure
        label="Supporting evidence"
        description="Metrics, memory hits, key events, workflow steps, and discrepancies."
      >
        <FactSection
          label="Metrics"
          items={[
            {
              label: "Run duration",
              value: formatDuration(run.metrics?.run_duration_ms),
            },
            {
              label: "Tool latency",
              value: formatLatencySummary(run.metrics?.tool_latency),
            },
            {
              label: "Retrieval latency",
              value: formatLatencySummary(
                run.metrics?.memory_retrieval_latency
              ),
            },
            {
              label: "Commit latency",
              value: formatLatencySummary(run.metrics?.memory_commit_latency),
            },
          ]}
        />

        <FactSection label="Memory counts" items={memoryCountItems} />

        <FactSection label="Memory outcomes" items={memoryOutcomeItems} />

        {memoryHits.length > 0 && (
          <section style={S.section}>
            <div style={S.sectionLabel}>Memory hits</div>
            <div style={S.memoryHitList}>
              {memoryHits.map((hit, index) => (
                <div key={`${hit.text}-${index}`} style={S.memoryHitCard}>
                  <div style={S.memoryHitTop}>
                    <span style={S.memoryHitScore}>{formatScore(hit.score)}</span>
                    <span style={S.memoryHitMeta}>
                      {[
                        hit.memory_type,
                        formatDateTime(hit.stored_at),
                      ]
                        .filter(Boolean)
                        .join(" • ") || "recorded memory"}
                    </span>
                  </div>
                  <div style={S.memoryHitText}>{hit.text}</div>
                </div>
              ))}
            </div>
          </section>
        )}

        {Array.isArray(run.key_events) && run.key_events.length > 0 && (
          <section style={S.section}>
            <div style={S.sectionLabel}>Key events</div>
            <div style={S.eventList}>
              {[...run.key_events].reverse().map((event, index) => (
                <div key={`${event.type}-${index}`} style={S.eventCard}>
                  <div style={S.eventTop}>
                    <span style={S.eventType}>{event.type}</span>
                    <span style={S.eventTime}>{formatDateTime(event.timestamp)}</span>
                  </div>
                  <div style={S.eventSummary}>{event.summary}</div>
                </div>
              ))}
            </div>
          </section>
        )}

        {Array.isArray(run.workflow_step_history) &&
          run.workflow_step_history.length > 0 && (
            <section style={S.section}>
              <div style={S.sectionLabel}>Workflow steps</div>
              <div style={S.stepList}>
                {workflowSteps.map((step, index) => (
                  <div key={step.step_id || step.action_id || `${index}`} style={S.stepCard}>
                    <div style={S.stepHeader}>
                      <div>
                        <div style={S.stepKey}>
                          {step.step_key || step.tool_name || `step ${index + 1}`}
                        </div>
                        <div style={S.stepSubline}>
                          {[
                            step.tool_name,
                            step.action_id,
                            step.receipt_id,
                          ]
                            .filter(Boolean)
                            .join(" • ") || "workflow step"}
                        </div>
                      </div>
                      <div style={S.stepMeta}>{step.status || "—"}</div>
                    </div>
                    {(hasValue(step.touched_paths) ||
                      hasValue(step.artifact_summaries)) && (
                      <div style={S.stepDetailRow}>
                        {Array.isArray(step.touched_paths) &&
                          step.touched_paths.length > 0 && (
                            <span style={S.stepToken}>
                              {step.touched_paths.length} touched path
                              {step.touched_paths.length === 1 ? "" : "s"}
                            </span>
                          )}
                        {Array.isArray(step.artifact_summaries) &&
                          step.artifact_summaries.length > 0 && (
                            <span style={S.stepToken}>
                              {step.artifact_summaries.length} artifact
                              {step.artifact_summaries.length === 1 ? "" : "s"}
                            </span>
                          )}
                      </div>
                    )}
                    {hasValue(step.mutation_result) && (
                      <pre style={S.payloadPreview}>
                        {formatPayload(step.mutation_result)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

        {Array.isArray(run.discrepancies) && run.discrepancies.length > 0 && (
          <section style={S.section}>
            <div style={S.sectionLabel}>Discrepancies</div>
            <div style={S.discrepancyBox}>{run.discrepancies.join("\n")}</div>
          </section>
        )}
      </OverviewDisclosure>
    </div>
  );
}

function OverviewDisclosure({ label, description, children }) {
  const [open, setOpen] = useState(false);

  return (
    <section className="runs-disclosure">
      <button
        className="runs-disclosureButton"
        onClick={() => setOpen((currentValue) => !currentValue)}
        type="button"
      >
        <div>
          <div className="runs-disclosureTitle">{label}</div>
          <div className="runs-disclosureDescription">{description}</div>
        </div>
        <span className="runs-disclosureToggle">{open ? "Hide" : "Show"}</span>
      </button>

      {open && <div className="runs-disclosureBody">{children}</div>}
    </section>
  );
}

function SubsystemStatusStrip({ subsystems, loading, error }) {
  if (loading) {
    return <PanelMessage text="Loading subsystem health…" />;
  }

  if (error) {
    return <PanelMessage text={error} tone="error" />;
  }

  if (!subsystems) {
    return null;
  }

  const memoryMode = formatSnakeLabel(
    subsystems.memory.memory_backend_mode ||
      (subsystems.memory.uses_sidecar ? "sidecar" : "local")
  );
  const memoryAvailability =
    typeof subsystems.memory.service_available === "boolean"
      ? subsystems.memory.service_available
        ? "service reachable"
        : "service unavailable"
      : null;
  const memoryHint = [
    memoryMode,
    memoryAvailability,
    subsystems.memory.service_url,
    subsystems.memory.detail,
  ]
    .filter(Boolean)
    .join(" • ");
  const databaseHint = [
    formatSnakeLabel(subsystems.database.mongo_scope),
    subsystems.database.detail,
  ]
    .filter(Boolean)
    .join(" • ");
  const autonomy = subsystems.autonomy || null;
  const formatControlPlaneLabel = (value, fallback = "None") => {
    if (!value) {
      return fallback;
    }
    const label = formatSnakeLabel(value);
    return label.charAt(0).toUpperCase() + label.slice(1).toLowerCase();
  };
  const lastCheckpointStatus = formatControlPlaneLabel(
    autonomy?.last_checkpoint?.status
  );
  const lastDecision = autonomy?.last_evaluator_decision
    ? formatControlPlaneLabel(autonomy.last_evaluator_decision)
    : formatControlPlaneLabel(autonomy?.last_checkpoint?.last_decision);
  const autonomyTone = autonomy?.kill_switch_active
    ? "danger"
    : (autonomy?.pending_escalations || 0) > 0
      ? "attention"
      : autonomy?.running
        ? "success"
        : "default";

  return (
    <section style={S.section}>
      <div style={S.panelHeaderRow}>
        <div style={S.sectionLabel}>Subsystem health</div>
        <div style={S.sectionCount}>{formatSnakeLabel(subsystems.status)}</div>
      </div>

      <MetricStrip
        compact
        items={[
          {
            label: "Environment",
            value: formatSnakeLabel(subsystems.status),
            hint: "backend, memory, storage, and LLM readiness",
            tone: toneForSubsystemStatus(subsystems.status),
          },
          {
            label: "Authority",
            value: formatSnakeLabel(subsystems.hca_runtime_authority),
            hint: `replay ${formatSnakeLabel(subsystems.replay_authority)}`,
            tone: "default",
          },
          {
            label: "Mongo",
            value: formatSnakeLabel(
              subsystems.database.mongo_status_mode || subsystems.database.status
            ),
            hint: databaseHint,
            tone: toneForSubsystemStatus(subsystems.database.status),
          },
          {
            label: "Memory",
            value: memoryMode,
            hint: memoryHint,
            tone: toneForSubsystemStatus(subsystems.memory.status),
          },
          {
            label: "Storage",
            value: formatSnakeLabel(subsystems.storage.status),
            hint: subsystems.storage.detail,
            tone: toneForSubsystemStatus(subsystems.storage.status),
          },
          {
            label: "LLM",
            value: formatSnakeLabel(subsystems.llm.status),
            hint: subsystems.llm.detail,
            tone: toneForSubsystemStatus(subsystems.llm.status),
          },
        ]}
      />

      {autonomy ? (
        <section style={{ ...S.section, marginTop: 12, padding: 0, border: "none" }}>
          <div style={S.panelHeaderRow}>
            <div style={S.sectionLabel}>Autonomy control plane</div>
            <div style={S.sectionCount}>{lastCheckpointStatus}</div>
          </div>
          <MetricStrip
            compact
            items={[
              {
                label: "Kill switch",
                value: autonomy.kill_switch_active ? "Active" : "Clear",
                hint:
                  autonomy.kill_switch_reason ||
                  (autonomy.kill_switch_active
                    ? "new and continued autonomy are blocked"
                    : "bounded autonomy may run within policy"),
                tone: autonomy.kill_switch_active ? "danger" : "success",
              },
              {
                label: "Pending escalations",
                value: String(autonomy.pending_escalations || 0),
                hint:
                  (autonomy.pending_escalations || 0) > 0
                    ? "operator approval is currently required"
                    : "no approval backlog",
                tone:
                  (autonomy.pending_escalations || 0) > 0
                    ? "attention"
                    : "default",
              },
              {
                label: "Active autonomous runs",
                value: String(autonomy.active_runs || 0),
                hint: `${autonomy.pending_triggers || 0} pending triggers • ${autonomy.dedupe_keys_tracked || 0} dedupe keys tracked`,
                tone: autonomyTone,
              },
              {
                label: "Last decision",
                value: lastDecision,
                hint: autonomy.loop_running
                  ? "supervisor loop running"
                  : "supervisor loop idle",
                tone: autonomyTone,
              },
              {
                label: "Checkpoint",
                value: lastCheckpointStatus,
                hint:
                  autonomy.last_checkpoint?.last_state
                    ? `last state ${formatSnakeLabel(autonomy.last_checkpoint.last_state)}`
                    : "no checkpoint recorded",
                tone: autonomyTone,
              },
              {
                label: "Budget ledgers",
                value: String(autonomy.budget_ledgers?.length || 0),
                hint:
                  autonomy.budget_ledgers?.length > 0
                    ? `${autonomy.budget_ledgers[0].total_steps_observed || 0} observed steps • ${autonomy.budget_ledgers[0].total_retries_used || 0} retries`
                    : "no budget usage recorded yet",
                tone: "default",
              },
            ]}
          />
        </section>
      ) : null}
    </section>
  );
}

function ReplayDigestCard({ run }) {
  const signal = summarizeRunSignal(run);
  const actionTaken = run.action_taken || {};
  const critique = run.critique || {};
  const { request } = getApprovalContext(run);
  const insightItems = [
    critique.verdict
      ? {
          tone:
            critique.verdict === "approved"
              ? "success"
              : critique.verdict === "revise"
                ? "attention"
                : "default",
          label: "Critique",
          text: `${formatSnakeLabel(critique.verdict)}${
            critique.issues?.length ? ` • ${critique.issues[0]}` : ""
          }`,
        }
      : null,
    hasValue(run.approval_id)
      ? {
          tone: "attention",
          label: "Approval",
          text:
            request?.reason ||
            `${actionTaken.kind || run.plan?.action || "Action"} is waiting for operator sign-off.`,
        }
      : null,
    Array.isArray(run.discrepancies) && run.discrepancies.length > 0
      ? {
          tone: "danger",
          label: "Discrepancies",
          text: `${run.discrepancies.length} replay mismatch${
            run.discrepancies.length === 1 ? "" : "es"
          } detected.`,
        }
      : null,
  ].filter(Boolean);

  return (
    <section className="runs-digestCard">
      <div style={S.digestHeader}>
        <div>
          <div style={S.digestEyebrow}>Replay digest</div>
          <div style={S.digestTitle}>{run.goal}</div>
          <div style={S.digestSummary}>{signal.summary}</div>
        </div>
        <span
          style={{
            ...S.focusBadge,
            color: signal.badge.color,
            background: signal.badge.bg,
            borderColor: signal.badge.border,
          }}
        >
          {signal.label}
        </span>
      </div>

      <MetricStrip
        compact
        items={[
          {
            label: "Action",
            value: actionTaken.kind || run.plan?.action || "—",
            hint: formatStrategyLabel(run.plan?.strategy) || "No strategy",
          },
          {
            label: "Latest receipt",
            value: run.latest_receipt?.status || run.action_result?.status || "—",
            hint: run.workflow_outcome?.terminal_event || "no terminal receipt",
          },
          {
            label: "Approval",
            value: formatApprovalStatus(run),
            hint: formatBoolean(actionTaken.requires_approval),
            mono: hasValue(run.approval_id),
          },
          {
            label: "Latency",
            value: formatDuration(run.metrics?.run_duration_ms),
            hint: formatLatencySummary(run.metrics?.tool_latency),
          },
          {
            label: "Events",
            value: String(run.event_count ?? 0),
            hint: `${run.key_events?.length || 0} key signals`,
          },
          {
            label: "Artifacts",
            value: String(run.artifacts_count ?? 0),
            hint: `${run.workflow_artifacts?.length || 0} workflow-linked`,
          },
        ]}
      />

      {insightItems.length > 0 && (
        <div style={S.insightList}>
          {insightItems.map((item) => (
            <div
              key={`${item.label}-${item.text}`}
              style={{
                ...S.insightCard,
                ...(item.tone === "attention"
                  ? S.insightCardAttention
                  : item.tone === "danger"
                    ? S.insightCardDanger
                    : item.tone === "success"
                      ? S.insightCardSuccess
                      : null),
              }}
            >
              <div style={S.insightLabel}>{item.label}</div>
              <div style={S.insightText}>{item.text}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function EventsPanel({ events, total }) {
  const [eventQuery, setEventQuery] = useState("");
  const [eventTypeFilter, setEventTypeFilter] = useState(FILTER_ALL);
  const [selectedEventId, setSelectedEventId] = useState(null);
  const [keyEventsOnly, setKeyEventsOnly] = useState(false);

  useEffect(() => {
    setEventQuery("");
    setEventTypeFilter(FILTER_ALL);
    setSelectedEventId(null);
    setKeyEventsOnly(false);
  }, [events]);

  const eventTypeOptions = Object.entries(
    events.reduce((accumulator, event) => {
      accumulator[event.event_type] = (accumulator[event.event_type] || 0) + 1;
      return accumulator;
    }, {})
  ).sort((left, right) => right[1] - left[1]);
  const filteredEvents = events.filter((event) => {
    if (keyEventsOnly && !event.is_key_event) {
      return false;
    }

    if (
      eventTypeFilter !== FILTER_ALL &&
      event.event_type !== eventTypeFilter
    ) {
      return false;
    }

    if (!matchesQueryText(eventQuery, [
      event.event_type,
      event.summary,
      event.actor,
      event.prior_state,
      event.next_state,
      safeJsonStringify(event.payload),
    ])) {
      return false;
    }

    return true;
  });
  const selectedEvent = filteredEvents.find(
    (event) => event.event_id === selectedEventId
  ) || filteredEvents[0] || null;

  useEffect(() => {
    if (filteredEvents.length === 0) {
      if (selectedEventId !== null) {
        setSelectedEventId(null);
      }
      return;
    }

    if (!filteredEvents.some((event) => event.event_id === selectedEventId)) {
      setSelectedEventId(filteredEvents[0].event_id);
    }
  }, [filteredEvents, selectedEventId]);

  return (
    <div style={S.detailBody}>
      <MetricStrip
        compact
        items={[
          {
            label: "Loaded",
            value: events.length,
            hint: total > events.length ? `of ${total} total` : "full event slice",
          },
          {
            label: "Key events",
            value: events.filter((event) => event.is_key_event).length,
            hint: keyEventsOnly ? "key-only filter active" : "operator-worthy markers",
            tone: "attention",
          },
          {
            label: "Visible",
            value: filteredEvents.length,
            hint: eventTypeFilter === FILTER_ALL ? "all event types" : formatSnakeLabel(eventTypeFilter),
          },
        ]}
      />

      <div style={S.panelHeaderRow}>
        <div style={S.sectionLabel}>Events ({total})</div>
        <div style={S.sectionCount}>
          {total > events.length
            ? `Latest ${events.length} loaded`
            : `${filteredEvents.length} visible`}
        </div>
      </div>

      {events.length === 0 && <PanelMessage text="No events recorded." />}

      {events.length > 0 && (
        <>
          <div style={S.toolbarRow}>
            <input
              aria-label="Filter events"
              placeholder="Filter by type, actor, summary, or payload"
              style={S.toolbarInput}
              value={eventQuery}
              onChange={(event) => setEventQuery(event.target.value)}
            />
            <button
              type="button"
              aria-pressed={keyEventsOnly}
              onClick={() => setKeyEventsOnly((currentValue) => !currentValue)}
              style={{
                ...S.toggleBtn,
                ...(keyEventsOnly ? S.toggleBtnActive : null),
              }}
            >
              Key only
            </button>
          </div>

          <div style={S.filterChipRow}>
            <button
              type="button"
              aria-pressed={eventTypeFilter === FILTER_ALL}
              onClick={() => setEventTypeFilter(FILTER_ALL)}
              style={{
                ...S.filterChip,
                ...(eventTypeFilter === FILTER_ALL ? S.filterChipActive : null),
              }}
            >
              All types
            </button>
            {eventTypeOptions.map(([eventType, count]) => (
              <button
                key={eventType}
                type="button"
                aria-pressed={eventTypeFilter === eventType}
                onClick={() => setEventTypeFilter(eventType)}
                style={{
                  ...S.filterChip,
                  ...(eventTypeFilter === eventType ? S.filterChipActive : null),
                }}
              >
                {eventType} · {count}
              </button>
            ))}
          </div>

          {filteredEvents.length === 0 && (
            <PanelMessage text="No events match the current filters." />
          )}

          {filteredEvents.length > 0 && (
            <>
              <div style={S.selectionList}>
                {filteredEvents.map((event) => {
                  const isSelected = event.event_id === selectedEvent?.event_id;

                  return (
                    <button
                      key={event.event_id}
                      type="button"
                      onClick={() => setSelectedEventId(event.event_id)}
                      style={{
                        ...S.selectionCard,
                        ...(isSelected ? S.selectionCardActive : null),
                      }}
                    >
                      <div style={S.eventTop}>
                        <div style={S.selectionHeading}>
                          <span style={S.eventType}>{event.event_type}</span>
                          {event.is_key_event && (
                            <span style={S.selectionPill}>Key</span>
                          )}
                        </div>
                        <span style={S.eventTime}>
                          {formatDateTime(event.timestamp)}
                        </span>
                      </div>
                      <div style={S.eventSummary}>{event.summary}</div>
                      <div style={S.eventMeta}>
                        <span>{event.actor || "unknown actor"}</span>
                        <span>
                          {event.prior_state || "—"} → {event.next_state || "—"}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>

              {selectedEvent && (
                <div style={S.inspectorCard}>
                  <div style={S.inspectorHeader}>
                    <div>
                      <div style={S.sectionLabel}>Selected event</div>
                      <div style={S.inspectorTitle}>{selectedEvent.summary}</div>
                    </div>
                    <span style={S.selectionPill}>{selectedEvent.event_type}</span>
                  </div>
                  <div style={S.infoGrid}>
                    <SummaryField label="Event ID" value={selectedEvent.event_id} mono />
                    <SummaryField label="Actor" value={selectedEvent.actor || "—"} />
                    <SummaryField
                      label="Timestamp"
                      value={formatDateTime(selectedEvent.timestamp)}
                    />
                    <SummaryField
                      label="Key event"
                      value={formatBoolean(selectedEvent.is_key_event)}
                    />
                    <SummaryField
                      label="State change"
                      value={`${selectedEvent.prior_state || "—"} → ${selectedEvent.next_state || "—"}`}
                    />
                  </div>
                  <pre style={S.payloadPreview}>{formatPayload(selectedEvent.payload)}</pre>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

function ArtifactsPanel({
  artifacts,
  artifactDetail,
  artifactError,
  artifactLoading,
  selectedArtifactId,
  total,
  onSelectArtifact,
}) {
  const [artifactQuery, setArtifactQuery] = useState("");
  const [artifactKindFilter, setArtifactKindFilter] = useState(FILTER_ALL);

  useEffect(() => {
    setArtifactQuery("");
    setArtifactKindFilter(FILTER_ALL);
  }, [artifacts]);

  const artifactKinds = Array.from(
    new Set(artifacts.map((artifact) => artifact.kind).filter(Boolean))
  );
  const filteredArtifacts = artifacts.filter((artifact) => {
    if (
      artifactKindFilter !== FILTER_ALL &&
      artifact.kind !== artifactKindFilter
    ) {
      return false;
    }

    if (!matchesQueryText(artifactQuery, [
      artifact.kind,
      artifact.path,
      artifact.action_id,
      artifact.workflow_id,
      artifact.approval_id,
    ])) {
      return false;
    }

    return true;
  });

  useEffect(() => {
    if (filteredArtifacts.length === 0) {
      if (selectedArtifactId !== null) {
        onSelectArtifact(null);
      }
      return;
    }

    if (
      !filteredArtifacts.some(
        (artifact) => artifact.artifact_id === selectedArtifactId
      )
    ) {
      onSelectArtifact(filteredArtifacts[0].artifact_id);
    }
  }, [filteredArtifacts, onSelectArtifact, selectedArtifactId]);

  return (
    <div style={S.detailBody}>
      <MetricStrip
        compact
        items={[
          {
            label: "Loaded",
            value: artifacts.length,
            hint: total > artifacts.length ? `of ${total} total` : "full artifact slice",
          },
          {
            label: "Previewable",
            value: artifacts.filter((artifact) => artifact.content_available).length,
            hint: "inline preview ready",
            tone: "success",
          },
          {
            label: "Kinds",
            value: artifactKinds.length,
            hint:
              artifactKindFilter === FILTER_ALL
                ? "all artifact families"
                : formatSnakeLabel(artifactKindFilter),
          },
        ]}
      />

      <div style={S.panelHeaderRow}>
        <div style={S.sectionLabel}>Artifacts ({total})</div>
        <div style={S.sectionCount}>
          {total > artifacts.length
            ? `Latest ${artifacts.length} loaded`
            : `${filteredArtifacts.length} visible`}
        </div>
      </div>

      {artifacts.length === 0 && <PanelMessage text="No artifacts stored." />}

      {artifacts.length > 0 && (
        <>
          <div style={S.toolbarRow}>
            <input
              aria-label="Filter artifacts"
              placeholder="Filter by kind, path, workflow, or action"
              style={S.toolbarInput}
              value={artifactQuery}
              onChange={(event) => setArtifactQuery(event.target.value)}
            />
          </div>

          <div style={S.filterChipRow}>
            <button
              type="button"
              aria-pressed={artifactKindFilter === FILTER_ALL}
              onClick={() => setArtifactKindFilter(FILTER_ALL)}
              style={{
                ...S.filterChip,
                ...(artifactKindFilter === FILTER_ALL ? S.filterChipActive : null),
              }}
            >
              All kinds
            </button>
            {artifactKinds.map((kind) => (
              <button
                key={kind}
                type="button"
                aria-pressed={artifactKindFilter === kind}
                onClick={() => setArtifactKindFilter(kind)}
                style={{
                  ...S.filterChip,
                  ...(artifactKindFilter === kind ? S.filterChipActive : null),
                }}
              >
                {kind}
              </button>
            ))}
          </div>

          {filteredArtifacts.length === 0 && (
            <PanelMessage text="No artifacts match the current filters." />
          )}

          {filteredArtifacts.length > 0 && (
            <div style={S.artifactList}>
              {filteredArtifacts.map((artifact) => (
              <button
                key={artifact.artifact_id}
                type="button"
                onClick={() => onSelectArtifact(artifact.artifact_id)}
                style={{
                  ...S.selectionCard,
                  ...(artifact.artifact_id === selectedArtifactId
                    ? S.selectionCardActive
                    : null),
                }}
              >
                <div style={S.artifactTop}>
                  <div style={S.selectionHeading}>
                    <span style={S.artifactKind}>{artifact.kind}</span>
                    {artifact.content_available && (
                      <span style={S.selectionPill}>Preview</span>
                    )}
                  </div>
                  <span style={S.artifactTime}>
                    {formatDateTime(artifact.created_at)}
                  </span>
                </div>
                <div style={S.artifactPath}>{artifact.path}</div>
                <div style={S.eventMeta}>
                  <span>{artifact.action_id}</span>
                  <span>
                    {artifact.file_paths?.length || 0} file path
                    {(artifact.file_paths?.length || 0) === 1 ? "" : "s"}
                  </span>
                </div>
              </button>
              ))}
            </div>
          )}

          {artifactLoading && <PanelMessage text="Loading artifact…" />}
          {!artifactLoading && artifactError && (
            <PanelMessage text={artifactError} tone="error" />
          )}
          {!artifactLoading && !artifactError && artifactDetail && (
            <div style={S.artifactDetail}>
              <div style={S.artifactDetailHeader}>
                <div style={S.artifactDetailTitle}>{artifactDetail.path}</div>
                <div style={S.artifactDetailMeta}>
                  {artifactDetail.size_bytes} bytes
                  {artifactDetail.truncated ? " • preview truncated" : ""}
                </div>
              </div>
              <div style={S.infoGrid}>
                <SummaryField label="Kind" value={artifactDetail.kind} />
                <SummaryField
                  label="Action id"
                  value={artifactDetail.action_id}
                  mono
                />
                <SummaryField
                  label="Workflow"
                  value={artifactDetail.workflow_id || "—"}
                  mono
                />
                <SummaryField
                  label="Approval"
                  value={artifactDetail.approval_id || "—"}
                  mono
                />
                <SummaryField
                  label="Content"
                  value={artifactDetail.content_available ? "available" : "none"}
                />
                <SummaryField
                  label="File paths"
                  value={String(artifactDetail.file_paths?.length || 0)}
                />
              </div>
              {Array.isArray(artifactDetail.source_action_ids) &&
                artifactDetail.source_action_ids.length > 0 && (
                  <section style={S.section}>
                    <div style={S.sectionLabel}>Source actions</div>
                    <TokenList values={artifactDetail.source_action_ids} mono />
                  </section>
                )}
              {Array.isArray(artifactDetail.file_paths) &&
                artifactDetail.file_paths.length > 0 && (
                  <section style={S.section}>
                    <div style={S.sectionLabel}>Linked files</div>
                    <TokenList values={artifactDetail.file_paths} mono />
                  </section>
                )}
              {hasValue(artifactDetail.hashes) && (
                <section style={S.section}>
                  <div style={S.sectionLabel}>Hashes</div>
                  <pre style={S.payloadPreview}>
                    {formatPayload(artifactDetail.hashes)}
                  </pre>
                </section>
              )}
              {hasValue(artifactDetail.metadata) && (
                <section style={S.section}>
                  <div style={S.sectionLabel}>Metadata</div>
                  <pre style={S.payloadPreview}>
                    {formatPayload(artifactDetail.metadata)}
                  </pre>
                </section>
              )}
              <pre style={S.artifactContent}>{artifactDetail.content || ""}</pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SummaryField({ label, value, mono = false }) {
  return (
    <div style={S.summaryField}>
      <div style={S.summaryLabel}>{label}</div>
      <div style={{ ...S.summaryValue, ...(mono ? S.summaryMono : null) }}>
        {value}
      </div>
    </div>
  );
}

function MetricStrip({ items, compact = false }) {
  const visibleItems = items.filter((item) => hasValue(item?.value));

  if (visibleItems.length === 0) {
    return null;
  }

  return (
    <div style={{ ...S.metricStrip, ...(compact ? S.metricStripCompact : null) }}>
      {visibleItems.map((item) => (
        <div
          key={item.label}
          style={{
            ...S.metricCard,
            ...(compact ? S.metricCardCompact : null),
            ...(item.tone === "attention"
              ? S.metricCardAttention
              : item.tone === "danger"
                ? S.metricCardDanger
                : item.tone === "success"
                  ? S.metricCardSuccess
                  : null),
          }}
        >
          <div style={S.metricLabel}>{item.label}</div>
          <div style={{ ...S.metricValue, ...(item.mono ? S.summaryMono : null) }}>
            {item.value}
          </div>
          {hasValue(item.hint) && <div style={S.metricHint}>{item.hint}</div>}
        </div>
      ))}
    </div>
  );
}

function PanelMessage({ text, tone = "default" }) {
  return (
    <div
      className={`runs-panelMessage${tone === "error" ? " is-error" : ""}`}
    >
      {text}
    </div>
  );
}

function FactSection({ label, items }) {
  const visibleItems = items.filter((item) => hasValue(item?.value));

  if (visibleItems.length === 0) {
    return null;
  }

  return (
    <section style={S.section}>
      <div style={S.sectionLabel}>{label}</div>
      <div style={S.infoGrid}>
        {visibleItems.map((item) => (
          <SummaryField
            key={item.label}
            label={item.label}
            value={item.value}
            mono={item.mono}
          />
        ))}
      </div>
    </section>
  );
}

function TokenList({ values, mono = false }) {
  return (
    <div style={S.tokenList}>
      {values.map((value) => (
        <span
          key={value}
          style={{ ...S.tokenChip, ...(mono ? S.summaryMono : null) }}
        >
          {value}
        </span>
      ))}
    </div>
  );
}

function hasValue(value) {
  if (value === null || value === undefined) {
    return false;
  }

  if (typeof value === "string") {
    return value.trim().length > 0;
  }

  if (Array.isArray(value)) {
    return value.length > 0;
  }

  if (typeof value === "object") {
    return Object.keys(value).length > 0;
  }

  return true;
}

function summarizeValue(value) {
  if (!hasValue(value)) {
    return "—";
  }

  if (Array.isArray(value)) {
    return `${value.length} item${value.length === 1 ? "" : "s"}`;
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (typeof value === "object") {
    return `${Object.keys(value).length} field${
      Object.keys(value).length === 1 ? "" : "s"
    }`;
  }

  return String(value);
}

function formatSnakeLabel(value) {
  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function formatStrategyLabel(value) {
  if (!value) {
    return "";
  }

  return STRATEGY_LABELS[value] || formatSnakeLabel(value);
}

function formatStateLabel(value) {
  if (!value) {
    return "—";
  }

  return formatSnakeLabel(value);
}

function formatBoolean(value) {
  return value ? "Yes" : "No";
}

function formatScore(value) {
  if (typeof value !== "number") {
    return "—";
  }

  return value.toFixed(2);
}

function formatSignedNumber(value) {
  if (typeof value !== "number") {
    return "—";
  }

  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

function formatConfidence(value) {
  if (typeof value !== "number") {
    return "—";
  }

  return `${Math.round(value * 100)}%`;
}

function formatDuration(value) {
  if (typeof value !== "number") {
    return "—";
  }

  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)} s`;
  }

  return `${Math.round(value)} ms`;
}

function formatLatencySummary(summary) {
  if (!summary || typeof summary.count !== "number" || summary.count === 0) {
    return "—";
  }

  const parts = [`${summary.count} sample${summary.count === 1 ? "" : "s"}`];

  if (typeof summary.last_ms === "number") {
    parts.push(`${summary.last_ms.toFixed(1)} ms last`);
  }

  if (typeof summary.max_ms === "number") {
    parts.push(`${summary.max_ms.toFixed(1)} ms max`);
  }

  return parts.join(" • ");
}

function formatWorkflowBudget(budget) {
  if (!hasValue(budget)) {
    return "—";
  }

  const maxSteps = budget.max_steps ?? "—";
  const consumedSteps = budget.consumed_steps ?? 0;
  return `${consumedSteps}/${maxSteps} steps`;
}

function formatWorkflowCheckpoint(checkpoint) {
  if (!hasValue(checkpoint)) {
    return "—";
  }

  const parts = [
    checkpoint.current_step_id,
    typeof checkpoint.current_step_index === "number"
      ? `index ${checkpoint.current_step_index}`
      : null,
  ].filter(Boolean);

  return parts.join(" • ") || "—";
}

function formatWorkflowOutcome(outcome) {
  if (!hasValue(outcome)) {
    return "—";
  }

  const parts = [
    outcome.terminal_event,
    outcome.reason,
    outcome.next_step_id ? `next ${outcome.next_step_id}` : null,
  ].filter(Boolean);

  return parts.join(" • ") || "—";
}

function formatApprovalStatus(run) {
  if (!run) {
    return "—";
  }

  if (run.approval?.status) {
    if (run.approval?.status === "pending" && run.approval_id) {
      return `pending (${run.approval_id})`;
    }

    return run.approval.status;
  }

  if (run.last_approval_decision) {
    return run.last_approval_decision;
  }

  if (run.approval_id) {
    return `pending (${run.approval_id})`;
  }

  return "—";
}

function toneForSubsystemStatus(status) {
  if (["healthy", "configured", "writable"].includes(status)) {
    return "success";
  }

  if (["degraded", "disabled", "missing"].includes(status)) {
    return "attention";
  }

  if (["unhealthy", "unavailable"].includes(status)) {
    return "danger";
  }

  return "default";
}

function getApprovalContext(run) {
  const approval =
    run?.approval && typeof run.approval === "object" ? run.approval : null;

  const request =
    approval?.request && typeof approval.request === "object"
      ? approval.request
      : null;
  const decision =
    approval?.decision && typeof approval.decision === "object"
      ? approval.decision
      : null;
  const grant =
    approval?.grant && typeof approval.grant === "object"
      ? approval.grant
      : null;
  const consumption =
    approval?.consumption && typeof approval.consumption === "object"
      ? approval.consumption
      : null;
  const binding =
    request?.binding ||
    grant?.binding ||
    decision?.binding ||
    consumption?.binding ||
    null;

  return { approval, request, decision, grant, consumption, binding };
}

function approvalBindingTokens(binding) {
  if (!binding || typeof binding !== "object") {
    return [];
  }

  return [
    binding.tool_name ? `tool ${binding.tool_name}` : null,
    binding.target ? `target ${binding.target}` : null,
    binding.policy_fingerprint
      ? `policy ${shortenIdentifier(binding.policy_fingerprint)}`
      : null,
    binding.action_fingerprint
      ? `action ${shortenIdentifier(binding.action_fingerprint)}`
      : null,
  ].filter(Boolean);
}

function formatDateTime(value) {
  if (!value) {
    return "—";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }

  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatPayload(payload) {
  try {
    const serialized = JSON.stringify(payload || {}, null, 2);
    return serialized.length > 420
      ? `${serialized.slice(0, 420)}...`
      : serialized;
  } catch {
    return "{}";
  }
}

function safeJsonStringify(value) {
  try {
    return JSON.stringify(value || {});
  } catch {
    return "";
  }
}

function matchesQueryText(queryText, values) {
  const normalizedQuery = queryText.trim().toLowerCase();
  if (!normalizedQuery) {
    return true;
  }

  return values.some((value) =>
    String(value || "").toLowerCase().includes(normalizedQuery)
  );
}

function formatTabLabel(tab, count) {
  if (typeof count !== "number") {
    return formatSnakeLabel(tab);
  }

  return `${formatSnakeLabel(tab)}${count > 0 ? ` ${count}` : ""}`;
}

function shortenIdentifier(value) {
  if (!value) {
    return "—";
  }

  const text = String(value);
  return text.length > 18 ? `${text.slice(0, 8)}…${text.slice(-6)}` : text;
}

function summarizeRunPortfolio(runs) {
  return runs.reduce(
    (summary, run) => {
      if (run.state === "awaiting_approval") {
        summary.awaiting_approval += 1;
      } else if (run.state === "completed") {
        summary.completed += 1;
      } else if (run.state === "failed") {
        summary.failed += 1;
      } else if (run.state === "halted") {
        summary.halted += 1;
      }

      return summary;
    },
    {
      awaiting_approval: 0,
      completed: 0,
      failed: 0,
      halted: 0,
    }
  );
}

function summarizeRunSignal(run) {
  if (!run) {
    return {
      tone: "default",
      label: "Loading",
      summary: "Fetching the current replay-backed selection.",
      badge: DEFAULT_STATE_META,
    };
  }

  const badge = STATE_META[run.state] || DEFAULT_STATE_META;
  const actionLabel = run.action_taken?.kind || run.plan?.action || "action";

  if (run.state === "awaiting_approval") {
    return {
      tone: "attention",
      label: "Needs sign-off",
      summary: `${actionLabel} is waiting for operator approval before execution can resume.`,
      badge,
    };
  }

  if (run.state === "completed") {
    return {
      tone: "success",
      label: "Closed loop",
      summary: `${actionLabel} completed with replay data, receipts, and artifacts ready for review.`,
      badge,
    };
  }

  if (run.state === "failed") {
    return {
      tone: "danger",
      label: "Needs investigation",
      summary: `${actionLabel} failed. Check critique, discrepancies, and event history before retrying.`,
      badge,
    };
  }

  if (run.state === "halted") {
    return {
      tone: "danger",
      label: "Operator stopped",
      summary: `${actionLabel} was halted after a denial or stop condition. Replay is ready for review.`,
      badge,
    };
  }

  return {
    tone: "default",
    label: formatStateLabel(run.state),
    summary: `${actionLabel} is staged in the replay surface with ${run.event_count ?? 0} recorded events.`,
    badge,
  };
}

function isApprovalActionable(run) {
  if (!run || run.state !== "awaiting_approval") {
    return false;
  }

  if (!hasValue(run.approval_id)) {
    return false;
  }

  if (run.approval?.status && run.approval.status !== "pending") {
    return false;
  }

  return run.action_taken?.requires_approval !== false;
}

function summarizeOverviewHeadline(run) {
  const actionLabel = run.action_taken?.kind || run.plan?.action || "Action";

  switch (run.state) {
    case "awaiting_approval":
      return `${actionLabel} is blocked on operator approval.`;
    case "completed":
      return `${actionLabel} completed and the result is ready to review.`;
    case "failed":
      return `${actionLabel} failed and needs investigation.`;
    case "halted":
      return `${actionLabel} was halted before completion.`;
    default:
      return `${actionLabel} is still progressing through the run.`;
  }
}

function summarizeOverviewDescription(run) {
  const signal = summarizeRunSignal(run);

  switch (run.state) {
    case "awaiting_approval":
      return `${signal.summary} Review the approval request first, then open the reasoning details only if you need the full chain of context.`;
    case "completed":
      return `${signal.summary} Use the supporting evidence section for receipts, memory hits, and workflow steps, then jump to artifacts or events only if you need raw detail.`;
    case "failed":
    case "halted":
      return `${signal.summary} Start with the supporting evidence section, then open raw events if the summary is not enough.`;
    default:
      return `${signal.summary} The overview keeps the answer first and the deeper replay context one click away.`;
  }
}
const S = {
  root: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    padding: "18px 16px 16px",
    background:
      "linear-gradient(180deg, rgba(240,249,255,0.9) 0%, rgba(255,255,255,0.96) 28%, rgba(248,250,252,1) 100%)",
    gap: 12,
    overflow: "hidden",
  },
  header: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
  },
  eyebrow: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.14em",
    color: "#0891b2",
    fontWeight: 800,
    marginBottom: 4,
  },
  title: {
    fontSize: 22,
    fontWeight: 800,
    color: "#0f172a",
    letterSpacing: "-0.03em",
  },
  subtitle: {
    marginTop: 4,
    fontSize: 13,
    lineHeight: 1.5,
    color: "#64748b",
  },
  metricStrip: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
    gap: 8,
  },
  metricStripCompact: {
    gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  },
  metricCard: {
    border: "1px solid rgba(186,230,253,0.9)",
    background:
      "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(240,249,255,0.92) 100%)",
    borderRadius: 16,
    padding: "10px 12px",
    minWidth: 0,
  },
  metricCardCompact: {
    borderRadius: 14,
    padding: "9px 11px",
  },
  metricCardAttention: {
    borderColor: "#ddd6fe",
    background:
      "linear-gradient(180deg, rgba(250,245,255,0.98) 0%, rgba(245,243,255,0.92) 100%)",
  },
  metricCardSuccess: {
    borderColor: "#a7f3d0",
    background:
      "linear-gradient(180deg, rgba(240,253,244,0.98) 0%, rgba(236,253,245,0.92) 100%)",
  },
  metricCardDanger: {
    borderColor: "#fecaca",
    background:
      "linear-gradient(180deg, rgba(255,241,242,0.98) 0%, rgba(254,242,242,0.92) 100%)",
  },
  metricLabel: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    fontWeight: 800,
    color: "#64748b",
    marginBottom: 6,
  },
  metricValue: {
    fontSize: 18,
    lineHeight: 1.15,
    fontWeight: 800,
    color: "#0f172a",
    wordBreak: "break-word",
  },
  metricHint: {
    marginTop: 5,
    fontSize: 12,
    lineHeight: 1.4,
    color: "#64748b",
  },
  focusCard: {
    border: "1px solid rgba(186,230,253,0.95)",
    background:
      "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(239,246,255,0.95) 100%)",
    borderRadius: 20,
    padding: "14px 14px 12px",
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  focusCardAttention: {
    borderColor: "#ddd6fe",
    background:
      "linear-gradient(180deg, rgba(250,245,255,0.98) 0%, rgba(245,243,255,0.94) 100%)",
  },
  focusCardSuccess: {
    borderColor: "#a7f3d0",
    background:
      "linear-gradient(180deg, rgba(240,253,244,0.98) 0%, rgba(236,253,245,0.94) 100%)",
  },
  focusCardDanger: {
    borderColor: "#fecaca",
    background:
      "linear-gradient(180deg, rgba(255,241,242,0.98) 0%, rgba(254,242,242,0.94) 100%)",
  },
  focusHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
  },
  focusEyebrow: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    fontWeight: 800,
    color: "#475569",
    marginBottom: 4,
  },
  focusTitle: {
    fontSize: 18,
    lineHeight: 1.25,
    fontWeight: 800,
    color: "#0f172a",
  },
  focusSubtitle: {
    marginTop: 5,
    fontSize: 13,
    lineHeight: 1.5,
    color: "#475569",
  },
  focusBadge: {
    flexShrink: 0,
    border: "1px solid #cbd5e1",
    borderRadius: 999,
    padding: "6px 10px",
    fontSize: 11,
    lineHeight: 1.2,
    fontWeight: 800,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  digestCard: {
    border: "1px solid #dbeafe",
    borderRadius: 18,
    background:
      "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(248,250,252,0.96) 100%)",
    padding: 14,
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  digestHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
  },
  digestEyebrow: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    fontWeight: 800,
    color: "#0891b2",
    marginBottom: 4,
  },
  digestTitle: {
    fontSize: 22,
    lineHeight: 1.25,
    fontWeight: 800,
    color: "#0f172a",
  },
  digestSummary: {
    marginTop: 6,
    fontSize: 13,
    lineHeight: 1.55,
    color: "#475569",
  },
  insightList: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
    gap: 8,
  },
  insightCard: {
    border: "1px solid #e2e8f0",
    borderRadius: 14,
    background: "rgba(255,255,255,0.92)",
    padding: "10px 11px",
  },
  insightCardAttention: {
    borderColor: "#ddd6fe",
    background: "#faf5ff",
  },
  insightCardSuccess: {
    borderColor: "#a7f3d0",
    background: "#f0fdf4",
  },
  insightCardDanger: {
    borderColor: "#fecaca",
    background: "#fff1f2",
  },
  insightLabel: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    fontWeight: 800,
    color: "#64748b",
    marginBottom: 4,
  },
  insightText: {
    fontSize: 13,
    lineHeight: 1.45,
    color: "#0f172a",
  },
  refreshBtn: {
    border: "1px solid #bae6fd",
    background: "#ecfeff",
    color: "#0f766e",
    borderRadius: 999,
    padding: "7px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
  },
  searchRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
  },
  searchInput: {
    flex: 1,
    border: "1px solid #cbd5e1",
    borderRadius: 12,
    padding: "10px 12px",
    fontSize: 14,
    background: "rgba(255,255,255,0.86)",
    color: "#0f172a",
    outline: "none",
  },
  searchClearBtn: {
    border: "1px solid #cbd5e1",
    background: "#ffffff",
    color: "#334155",
    borderRadius: 10,
    padding: "0 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
  },
  runListHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  filterStack: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  filterChipRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
  },
  filterChip: {
    borderWidth: 1,
    borderStyle: "solid",
    borderColor: "#cbd5e1",
    background: "rgba(255,255,255,0.8)",
    color: "#475569",
    borderRadius: 999,
    padding: "6px 10px",
    fontSize: 11,
    fontWeight: 700,
    cursor: "pointer",
    lineHeight: 1.2,
  },
  filterChipActive: {
    borderColor: "#67e8f9",
    background: "#ecfeff",
    color: "#155e75",
  },
  noticeBar: {
    border: "1px solid #fde68a",
    background: "#fffbeb",
    color: "#92400e",
    borderRadius: 12,
    padding: "10px 12px",
    fontSize: 12,
    lineHeight: 1.5,
  },
  sectionLabel: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    color: "#64748b",
    fontWeight: 800,
  },
  sectionCount: {
    fontSize: 12,
    color: "#64748b",
  },
  runList: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    minHeight: 150,
    maxHeight: 240,
    overflowY: "auto",
    paddingRight: 4,
  },
  runRow: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    width: "100%",
    padding: "12px 12px 11px",
    borderRadius: 14,
    borderWidth: 1,
    borderStyle: "solid",
    borderColor: "#e2e8f0",
    background: "rgba(255,255,255,0.82)",
    cursor: "pointer",
    textAlign: "left",
  },
  runRowTop: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  runBadge: {
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    fontWeight: 800,
    padding: "4px 8px",
    borderRadius: 999,
    border: "1px solid transparent",
  },
  runTime: {
    fontSize: 11,
    color: "#64748b",
    whiteSpace: "nowrap",
  },
  runGoal: {
    fontSize: 14,
    fontWeight: 700,
    color: "#0f172a",
    lineHeight: 1.45,
  },
  runMeta: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
    fontSize: 12,
    color: "#64748b",
  },
  pagination: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  pageBtn: {
    border: "1px solid #cbd5e1",
    background: "#ffffff",
    color: "#334155",
    borderRadius: 10,
    padding: "6px 10px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
  },
  pageInfo: {
    fontSize: 12,
    color: "#64748b",
  },
  detailPanel: {
    display: "flex",
    flexDirection: "column",
    flex: 1,
    minHeight: 0,
    borderTop: "1px solid rgba(203,213,225,0.75)",
    paddingTop: 12,
  },
  tabs: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 12,
  },
  tab: {
    borderWidth: 1,
    borderStyle: "solid",
    borderColor: "#cbd5e1",
    background: "rgba(255,255,255,0.78)",
    color: "#475569",
    borderRadius: 999,
    padding: "7px 12px",
    fontSize: 12,
    fontWeight: 700,
    textTransform: "capitalize",
    cursor: "pointer",
  },
  tabActive: {
    borderColor: "#67e8f9",
    background: "#ecfeff",
    color: "#155e75",
  },
  detailBody: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
    overflowY: "auto",
    paddingRight: 4,
  },
  summaryCard: {
    border: "1px solid #e2e8f0",
    borderRadius: 16,
    padding: 14,
    background: "rgba(255,255,255,0.86)",
  },
  summaryGoal: {
    fontSize: 18,
    fontWeight: 800,
    color: "#0f172a",
    lineHeight: 1.35,
    marginBottom: 12,
  },
  summaryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: 10,
  },
  summaryField: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    minWidth: 0,
  },
  summaryLabel: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    color: "#64748b",
    fontWeight: 800,
  },
  summaryValue: {
    fontSize: 13,
    lineHeight: 1.45,
    color: "#0f172a",
    wordBreak: "break-word",
  },
  summaryMono: {
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 12,
  },
  infoGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: 10,
  },
  section: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  tokenList: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
  },
  tokenChip: {
    display: "inline-flex",
    alignItems: "center",
    maxWidth: "100%",
    padding: "6px 10px",
    borderRadius: 999,
    border: "1px solid #cbd5e1",
    background: "#f8fafc",
    color: "#334155",
    fontSize: 12,
    lineHeight: 1.4,
    wordBreak: "break-word",
  },
  eventList: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  panelHeaderRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: 8,
  },
  toolbarRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
  },
  focusActionCard: {
    border: "1px solid #ddd6fe",
    borderRadius: 16,
    background: "rgba(255,255,255,0.92)",
    padding: 12,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  focusActionHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: 8,
  },
  focusActionEyebrow: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    fontWeight: 800,
    color: "#7c3aed",
    marginBottom: 4,
  },
  focusActionTitle: {
    fontSize: 14,
    lineHeight: 1.45,
    fontWeight: 700,
    color: "#0f172a",
  },
  focusActionId: {
    display: "inline-flex",
    alignItems: "center",
    padding: "4px 8px",
    borderRadius: 999,
    border: "1px solid #ddd6fe",
    background: "#f5f3ff",
    color: "#6d28d9",
    fontSize: 11,
    fontWeight: 700,
    fontFamily: "'JetBrains Mono', monospace",
  },
  focusActionPayload: {
    margin: 0,
    padding: 12,
    borderRadius: 14,
    border: "1px solid #e2e8f0",
    background: "#f8fafc",
    color: "#0f172a",
    fontSize: 12,
    lineHeight: 1.55,
    fontFamily: "'JetBrains Mono', monospace",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  focusActionContext: {
    fontSize: 13,
    lineHeight: 1.55,
    color: "#475569",
  },
  focusActionButtons: {
    display: "flex",
    flexWrap: "wrap",
    gap: 10,
  },
  focusApproveBtn: {
    border: "1px solid #86efac",
    background: "#dcfce7",
    color: "#166534",
    borderRadius: 12,
    padding: "10px 14px",
    fontSize: 13,
    fontWeight: 800,
    cursor: "pointer",
  },
  focusDenyBtn: {
    border: "1px solid #fecaca",
    background: "#fee2e2",
    color: "#b91c1c",
    borderRadius: 12,
    padding: "10px 14px",
    fontSize: 13,
    fontWeight: 800,
    cursor: "pointer",
  },
  focusActionError: {
    border: "1px solid #fecaca",
    background: "#fff1f2",
    color: "#b91c1c",
    borderRadius: 12,
    padding: "10px 12px",
    fontSize: 12,
    lineHeight: 1.5,
  },
  toolbarInput: {
    flex: 1,
    border: "1px solid #cbd5e1",
    borderRadius: 12,
    padding: "10px 12px",
    fontSize: 13,
    background: "rgba(255,255,255,0.88)",
    color: "#0f172a",
    outline: "none",
  },
  toggleBtn: {
    borderWidth: 1,
    borderStyle: "solid",
    borderColor: "#cbd5e1",
    background: "#ffffff",
    color: "#334155",
    borderRadius: 10,
    padding: "0 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  toggleBtnActive: {
    borderColor: "#67e8f9",
    background: "#ecfeff",
    color: "#155e75",
  },
  selectionList: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  selectionCard: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    width: "100%",
    padding: 12,
    borderRadius: 14,
    borderWidth: 1,
    borderStyle: "solid",
    borderColor: "#e2e8f0",
    background: "rgba(255,255,255,0.82)",
    cursor: "pointer",
    textAlign: "left",
  },
  selectionCardActive: {
    borderColor: "#67e8f9",
    boxShadow: "0 0 0 1px rgba(6,182,212,0.12)",
    background: "rgba(236,254,255,0.78)",
  },
  selectionHeading: {
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 8,
  },
  selectionPill: {
    display: "inline-flex",
    alignItems: "center",
    padding: "4px 8px",
    borderRadius: 999,
    background: "#ecfeff",
    border: "1px solid #bae6fd",
    color: "#155e75",
    fontSize: 11,
    fontWeight: 700,
  },
  inspectorCard: {
    display: "flex",
    flexDirection: "column",
    gap: 10,
    border: "1px solid #bae6fd",
    background: "rgba(236,254,255,0.6)",
    borderRadius: 16,
    padding: 12,
  },
  inspectorHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 10,
  },
  inspectorTitle: {
    marginTop: 4,
    fontSize: 14,
    fontWeight: 700,
    color: "#0f172a",
    lineHeight: 1.45,
  },
  memoryHitList: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  memoryHitCard: {
    border: "1px solid #dbeafe",
    borderRadius: 14,
    padding: 12,
    background: "rgba(239,246,255,0.68)",
  },
  memoryHitTop: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    marginBottom: 6,
  },
  memoryHitScore: {
    fontSize: 12,
    fontWeight: 800,
    color: "#0f766e",
    fontFamily: "'JetBrains Mono', monospace",
  },
  memoryHitMeta: {
    fontSize: 11,
    color: "#64748b",
  },
  memoryHitText: {
    fontSize: 13,
    lineHeight: 1.55,
    color: "#0f172a",
  },
  eventCard: {
    border: "1px solid #e2e8f0",
    borderRadius: 14,
    padding: 12,
    background: "rgba(255,255,255,0.84)",
  },
  eventTop: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    marginBottom: 8,
  },
  eventType: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    color: "#155e75",
    fontWeight: 800,
  },
  eventTime: {
    fontSize: 11,
    color: "#64748b",
  },
  eventSummary: {
    fontSize: 13,
    lineHeight: 1.5,
    color: "#0f172a",
    marginBottom: 6,
  },
  eventMeta: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
    fontSize: 11,
    color: "#64748b",
    marginBottom: 8,
  },
  payloadPreview: {
    margin: 0,
    borderRadius: 12,
    background: "#f8fafc",
    border: "1px solid #e2e8f0",
    padding: "10px 12px",
    fontSize: 11,
    lineHeight: 1.55,
    color: "#334155",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  stepList: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  stepCard: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    padding: 12,
    border: "1px solid #e2e8f0",
    borderRadius: 12,
    background: "rgba(255,255,255,0.82)",
  },
  stepHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
  },
  stepKey: {
    fontSize: 13,
    fontWeight: 700,
    color: "#0f172a",
  },
  stepSubline: {
    marginTop: 4,
    fontSize: 11,
    color: "#64748b",
    lineHeight: 1.5,
    wordBreak: "break-word",
  },
  stepMeta: {
    fontSize: 12,
    color: "#475569",
    whiteSpace: "nowrap",
  },
  stepDetailRow: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
  },
  stepToken: {
    display: "inline-flex",
    alignItems: "center",
    padding: "4px 8px",
    borderRadius: 999,
    background: "#ecfeff",
    border: "1px solid #bae6fd",
    color: "#155e75",
    fontSize: 11,
    fontWeight: 700,
  },
  discrepancyBox: {
    border: "1px solid #fecaca",
    background: "#fff1f2",
    color: "#b91c1c",
    borderRadius: 14,
    padding: 12,
    fontSize: 12,
    lineHeight: 1.6,
    whiteSpace: "pre-wrap",
  },
  artifactList: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  artifactRow: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    width: "100%",
    padding: 12,
    borderRadius: 14,
    border: "1px solid #e2e8f0",
    background: "rgba(255,255,255,0.82)",
    cursor: "pointer",
    textAlign: "left",
  },
  artifactTop: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  artifactKind: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    color: "#0f766e",
    fontWeight: 800,
  },
  artifactTime: {
    fontSize: 11,
    color: "#64748b",
  },
  artifactPath: {
    fontSize: 12,
    lineHeight: 1.45,
    color: "#0f172a",
    wordBreak: "break-word",
  },
  artifactDetail: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    border: "1px solid #bae6fd",
    background: "rgba(236,254,255,0.6)",
    borderRadius: 16,
    padding: 12,
  },
  artifactDetailHeader: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  artifactDetailTitle: {
    fontSize: 13,
    fontWeight: 700,
    color: "#0f172a",
    wordBreak: "break-word",
  },
  artifactDetailMeta: {
    fontSize: 11,
    color: "#64748b",
  },
  artifactContent: {
    margin: 0,
    maxHeight: 240,
    overflow: "auto",
    borderRadius: 12,
    background: "#0f172a",
    color: "#e2e8f0",
    padding: "12px 14px",
    fontSize: 12,
    lineHeight: 1.55,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  message: {
    border: "1px solid #e2e8f0",
    borderRadius: 14,
    padding: "12px 14px",
    fontSize: 13,
    lineHeight: 1.5,
  },
};
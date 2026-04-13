import { useEffect, useState } from "react";
import {
  getRunArtifactDetail,
  getRunSummary,
  listRunArtifacts,
  listRunEvents,
  listRuns,
  toErrorMessage,
} from "@/lib/api";

const RUN_PAGE_SIZE = 10;
const EVENT_LIMIT = 80;
const ARTIFACT_LIMIT = 50;

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

export default function OperatorConsole({
  selectedRunId,
  onSelectRun,
  refreshToken,
}) {
  const [runs, setRuns] = useState([]);
  const [totalRuns, setTotalRuns] = useState(0);
  const [runQuery, setRunQuery] = useState("");
  const [runPage, setRunPage] = useState(0);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState("");

  const [runDetail, setRunDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

  const [events, setEvents] = useState([]);
  const [eventTotal, setEventTotal] = useState(0);
  const [artifacts, setArtifacts] = useState([]);
  const [artifactTotal, setArtifactTotal] = useState(0);

  const [activeTab, setActiveTab] = useState("overview");
  const [selectedArtifactId, setSelectedArtifactId] = useState(null);
  const [artifactDetail, setArtifactDetail] = useState(null);
  const [artifactLoading, setArtifactLoading] = useState(false);
  const [artifactError, setArtifactError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadRuns() {
      setRunsLoading(true);
      setRunsError("");

      try {
        const data = await listRuns({
          query: runQuery,
          limit: RUN_PAGE_SIZE,
          offset: runPage * RUN_PAGE_SIZE,
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
  }, [refreshToken, runPage, runQuery]);

  useEffect(() => {
    if (!selectedRunId && runs.length > 0) {
      onSelectRun?.(runs[0].run_id);
    }
  }, [onSelectRun, runs, selectedRunId]);

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
  }, [refreshToken, selectedRunId]);

  useEffect(() => {
    if (!selectedArtifactId && artifacts.length > 0) {
      setSelectedArtifactId(artifacts[0].artifact_id);
    }
  }, [artifacts, selectedArtifactId]);

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

  return (
    <aside style={S.root}>
      <div style={S.header}>
        <div>
          <div style={S.eyebrow}>Operator</div>
          <div style={S.title}>Replay Console</div>
          <div style={S.subtitle}>
            Recent runs, bounded event history, and stored artifacts.
          </div>
        </div>
        <button
          onClick={() => onSelectRun?.(selectedRunId || null)}
          style={S.refreshBtn}
          type="button"
        >
          Focus
        </button>
      </div>

      <div style={S.searchRow}>
        <input
          value={runQuery}
          onChange={(event) => {
            setRunQuery(event.target.value);
            setRunPage(0);
          }}
          placeholder="Search runs by goal or id"
          style={S.searchInput}
        />
      </div>

      <div style={S.runListHeader}>
        <span style={S.sectionLabel}>Runs</span>
        <span style={S.sectionCount}>{totalRuns}</span>
      </div>

      <div style={S.runList}>
        {runsLoading && <PanelMessage text="Loading runs…" />}
        {!runsLoading && runsError && <PanelMessage text={runsError} tone="error" />}
        {!runsLoading && !runsError && runs.length === 0 && (
          <PanelMessage text="No runs found." />
        )}
        {runs.map((run) => (
          <RunRow
            key={run.run_id}
            run={run}
            selected={run.run_id === selectedRunId}
            onClick={() => onSelectRun?.(run.run_id)}
          />
        ))}
      </div>

      {totalRuns > RUN_PAGE_SIZE && (
        <div style={S.pagination}>
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
              totalRuns
            )}
          </span>
          <button
            type="button"
            style={{
              ...S.pageBtn,
              opacity:
                (runPage + 1) * RUN_PAGE_SIZE >= totalRuns ? 0.4 : 1,
            }}
            disabled={(runPage + 1) * RUN_PAGE_SIZE >= totalRuns}
            onClick={() => setRunPage((currentValue) => currentValue + 1)}
          >
            Next
          </button>
        </div>
      )}

      <div style={S.detailPanel}>
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
              {tab}
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
      type="button"
      onClick={onClick}
      style={{
        ...S.runRow,
        borderColor: selected ? "#818cf8" : "#e2e8f0",
        boxShadow: selected ? "0 0 0 1px rgba(99,102,241,0.12)" : "none",
      }}
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
          {run.state}
        </span>
        <span style={S.runTime}>{formatDateTime(run.updated_at)}</span>
      </div>
      <div style={S.runGoal}>{run.goal}</div>
      <div style={S.runMeta}>
        <span>{run.plan?.strategy || "no strategy"}</span>
        <span>{run.event_count} events</span>
        <span>{run.artifacts_count} artifacts</span>
      </div>
    </button>
  );
}

function OverviewPanel({ run }) {
  const plan = run.plan || {};
  const perception = run.perception || {};
  const critique = run.critique || {};
  const actionTaken = run.action_taken || {};
  const actionResult = run.action_result || {};
  const activeWorkflow = run.active_workflow || {};
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

  return (
    <div style={S.detailBody}>
      <div style={S.summaryCard}>
        <div style={S.summaryGoal}>{run.goal}</div>
        <div style={S.summaryGrid}>
          <SummaryField label="Run ID" value={run.run_id} mono />
          <SummaryField label="State" value={run.state} />
          <SummaryField label="Created" value={formatDateTime(run.created_at)} />
          <SummaryField label="Updated" value={formatDateTime(run.updated_at)} />
          <SummaryField label="Strategy" value={plan.strategy || "—"} />
          <SummaryField
            label="Action"
            value={actionTaken.kind || plan.action || "—"}
          />
          <SummaryField
            label="Workflow"
            value={activeWorkflow.workflow_class || "—"}
          />
          <SummaryField
            label="Workflow outcome"
            value={formatWorkflowOutcome(workflowOutcome)}
          />
          <SummaryField
            label="Approval state"
            value={formatApprovalStatus(run)}
          />
          <SummaryField
            label="Latest Receipt"
            value={run.latest_receipt?.status || actionResult.status || "—"}
          />
          <SummaryField
            label="Approval required"
            value={formatBoolean(actionTaken.requires_approval)}
          />
          <SummaryField label="Events" value={String(run.event_count)} />
          <SummaryField
            label="Artifacts"
            value={String(run.artifacts_count)}
          />
          <SummaryField
            label="Discrepancies"
            value={String((run.discrepancies || []).length)}
          />
        </div>
      </div>

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

      {hasValue(actionTaken.arguments) && (
        <section style={S.section}>
          <div style={S.sectionLabel}>Action arguments</div>
          <pre style={S.payloadPreview}>{formatPayload(actionTaken.arguments)}</pre>
        </section>
      )}

      {memoryHits.length > 0 && (
        <section style={S.section}>
          <div style={S.sectionLabel}>Memory hits</div>
          <div style={S.memoryHitList}>
            {memoryHits.map((hit, index) => (
              <div
                key={`${hit.text}-${index}`}
                style={S.memoryHitCard}
              >
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
                <div
                  key={step.step_id || step.action_id || `${index}`}
                  style={S.stepCard}
                >
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
    </div>
  );
}

function EventsPanel({ events, total }) {
  return (
    <div style={S.detailBody}>
      <div style={S.sectionLabel}>Events ({total})</div>
      {events.length === 0 && <PanelMessage text="No events recorded." />}
      {events.length > 0 && (
        <div style={S.eventList}>
          {events.map((event) => (
            <div key={event.event_id} style={S.eventCard}>
              <div style={S.eventTop}>
                <span style={S.eventType}>{event.event_type}</span>
                <span style={S.eventTime}>{formatDateTime(event.timestamp)}</span>
              </div>
              <div style={S.eventSummary}>{event.summary}</div>
              <div style={S.eventMeta}>
                <span>{event.actor || "unknown actor"}</span>
                <span>
                  {event.prior_state || "—"} → {event.next_state || "—"}
                </span>
              </div>
              <pre style={S.payloadPreview}>{formatPayload(event.payload)}</pre>
            </div>
          ))}
        </div>
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
  return (
    <div style={S.detailBody}>
      <div style={S.sectionLabel}>Artifacts ({total})</div>
      {artifacts.length === 0 && <PanelMessage text="No artifacts stored." />}
      {artifacts.length > 0 && (
        <>
          <div style={S.artifactList}>
            {artifacts.map((artifact) => (
              <button
                key={artifact.artifact_id}
                type="button"
                onClick={() => onSelectArtifact(artifact.artifact_id)}
                style={{
                  ...S.artifactRow,
                  borderColor:
                    artifact.artifact_id === selectedArtifactId
                      ? "#67e8f9"
                      : "#e2e8f0",
                }}
              >
                <div style={S.artifactTop}>
                  <span style={S.artifactKind}>{artifact.kind}</span>
                  <span style={S.artifactTime}>
                    {formatDateTime(artifact.created_at)}
                  </span>
                </div>
                <div style={S.artifactPath}>{artifact.path}</div>
              </button>
            ))}
          </div>

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

function PanelMessage({ text, tone = "default" }) {
  return (
    <div
      style={{
        ...S.message,
        color: tone === "error" ? "#b91c1c" : "#475569",
        background: tone === "error" ? "#fff1f2" : "#f8fafc",
        borderColor: tone === "error" ? "#fecdd3" : "#e2e8f0",
      }}
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
  if (run.last_approval_decision) {
    return run.last_approval_decision;
  }

  if (run.approval_id) {
    return `pending (${run.approval_id})`;
  }

  return "—";
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
  },
  searchInput: {
    width: "100%",
    border: "1px solid #cbd5e1",
    borderRadius: 12,
    padding: "10px 12px",
    fontSize: 14,
    background: "rgba(255,255,255,0.86)",
    color: "#0f172a",
    outline: "none",
  },
  runListHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
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
    border: "1px solid #e2e8f0",
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
    gap: 8,
    marginBottom: 12,
  },
  tab: {
    border: "1px solid #cbd5e1",
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
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
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
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
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
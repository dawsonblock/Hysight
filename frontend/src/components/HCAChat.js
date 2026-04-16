import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./HCAChat.css";
import {
  decideRunApproval,
  getResponseErrorMessage,
  streamRun,
  toErrorMessage,
} from "@/lib/api";
import { summarizeApprovalToast } from "@/lib/run-presentation";
import { toast } from "@/hooks/use-toast";

// Events worth showing in the live trace (filter out internal plumbing)
const VISIBLE_EVENTS = new Set([
  "run_created",
  "module_proposed",
  "meta_assessed",
  "workflow_selected",
  "workflow_step_started",
  "workflow_step_finished",
  "workflow_budget_exhausted",
  "workflow_terminated",
  "action_selected",
  "approval_requested",
  "approval_granted",
  "approval_denied",
  "execution_started",
  "execution_finished",
  "memory_written",
  "run_completed",
  "run_failed",
]);

// ── Pipeline step config ──────────────────────────────────────────────────────

const STEP_ICONS = {
  run_created:        { icon: "◎", color: "#6366f1" },
  module_proposed:    { icon: "◈", color: "#0ea5e9" },
  meta_assessed:      { icon: "◇", color: "#8b5cf6" },
  workflow_selected:  { icon: "▣", color: "#0ea5e9" },
  workflow_step_started: {
    icon: "↳",
    color: "#14b8a6",
  },
  workflow_step_finished: {
    icon: "↴",
    color: "#10b981",
  },
  workflow_budget_exhausted: {
    icon: "⧖",
    color: "#d97706",
  },
  workflow_terminated: {
    icon: "⨯",
    color: "#dc2626",
  },
  action_scored:      { icon: "◆", color: "#8b5cf6" },
  action_selected:    { icon: "▷", color: "#f59e0b" },
  approval_requested: { icon: "⊛", color: "#ec4899" },
  approval_granted:   { icon: "⊕", color: "#10b981" },
  approval_denied:    { icon: "⊗", color: "#dc2626" },
  execution_started:  { icon: "▶", color: "#f97316" },
  execution_finished: { icon: "✓", color: "#10b981" },
  memory_written:     { icon: "⊕", color: "#14b8a6" },
  run_completed:      { icon: "●", color: "#10b981" },
  run_failed:         { icon: "✗", color: "#ef4444" },
  snapshot_saved:     { icon: "◉", color: "#94a3b8" },
};

const STATE_META = {
  completed:         { label: "COMPLETED",         color: "#059669", bg: "#ecfdf5", border: "#6ee7b7" },
  awaiting_approval: { label: "AWAITING APPROVAL", color: "#7c3aed", bg: "#f5f3ff", border: "#c4b5fd" },
  failed:            { label: "FAILED",             color: "#dc2626", bg: "#fef2f2", border: "#fca5a5" },
  halted:            { label: "HALTED",             color: "#d97706", bg: "#fffbeb", border: "#fcd34d" },
};

const STRATEGY_LABELS = {
  single_action_dispatch:         "Direct Dispatch",
  memory_persistence_strategy:    "Memory Write",
  information_retrieval_strategy: "Memory Retrieval",
  artifact_authoring_strategy:    "Artifact Creation",
};

const EXAMPLE_GOALS = [
  "Prepare a short release summary for the latest operator run",
  "Find what we stored about the database migration",
  "Draft a status update from the most recent replay artifacts",
  "Check whether anything is waiting for operator approval",
];

const RECENT_STEP_PREVIEW_COUNT = 4;

// ── Main component ────────────────────────────────────────────────────────────

export default function HCAChat({
  memPanelOpen,
  onToggleMemPanel,
  onRunObserved,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const updateMessageById = useCallback((messageId, updater) => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === messageId ? updater(message) : message
      )
    );
  }, []);

  const submitGoal = useCallback(async () => {
    const goal = input.trim();
    if (!goal || loading) return;
    setInput("");
    setLoading(true);

    const timestamp = Date.now();
    const userId = `u-${timestamp}`;
    const agentId = `a-${timestamp}`;
    setMessages((prev) => [
      ...prev,
      { type: "user", content: goal, id: userId },
      { type: "streaming", steps: [], id: agentId, goal },
    ]);

    try {
      const response = await streamRun(goal);

      if (!response.ok) {
        throw new Error(await getResponseErrorMessage(response));
      }

      if (!response.body) {
        throw new Error("Streaming response body was unavailable.");
      }

      const reader  = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer    = "";

      const parseEvent = (chunk) => {
        // SSE format: "event: <type>\ndata: <json>\n\n"
        const eventMatch = chunk.match(/^event:\s*(.+)$/m);
        const dataMatch  = chunk.match(/^data:\s*(.+)$/m);
        if (!eventMatch || !dataMatch) return null;
        try {
          return { eventType: eventMatch[1].trim(), data: JSON.parse(dataMatch[1].trim()) };
        } catch {
          return null;
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() || "";

        for (const chunk of chunks) {
          if (!chunk.trim()) continue;
          const parsed = parseEvent(chunk);
          if (!parsed) continue;
          const { eventType, data } = parsed;

          if (eventType === "step") {
            if (!VISIBLE_EVENTS.has(data.event_type)) continue; // filter internals
            updateMessageById(agentId, (currentMessage) => ({
              ...currentMessage,
              steps: [...currentMessage.steps, data],
            }));
          } else if (eventType === "status") {
            if (typeof data?.run_id === "string") {
              onRunObserved?.(data.run_id);
            }
          } else if (eventType === "done") {
            if (typeof data?.run_id === "string") {
              onRunObserved?.(data.run_id);
            }
            showRunToast(data);
            updateMessageById(agentId, (currentMessage) => ({
              ...currentMessage,
              type: "agent",
              summary: data,
              _actionPending: null,
              actionError: "",
            }));
          } else if (eventType === "error") {
            toast({
              title: "Run failed",
              description: data.label || "The agent reported an execution error.",
              variant: "destructive",
            });
            updateMessageById(agentId, (currentMessage) => ({
              ...currentMessage,
              type: "error",
              content: data.label,
            }));
          }
        }
      }
    } catch (error) {
      const message = toErrorMessage(error, "Request failed.");
      toast({
        title: "Run failed to start",
        description: message,
        variant: "destructive",
      });
      updateMessageById(agentId, (currentMessage) => ({
        ...currentMessage,
        type: "error",
        content: message,
      }));
    } finally {
      setLoading(false);
    }
  }, [input, loading, onRunObserved, updateMessageById]);

  const resolveAction = useCallback(async (decision, runId, approvalId, agentId) => {
    updateMessageById(agentId, (currentMessage) => ({
      ...currentMessage,
      _actionPending: decision,
      actionError: "",
    }));

    try {
      const data = await decideRunApproval(runId, decision, approvalId);

      toast({
        title: decision === "approve" ? "Approval granted" : "Approval denied",
        description: summarizeApprovalToast(data, decision),
        variant: data?.state === "failed" ? "destructive" : "default",
      });

      updateMessageById(agentId, (currentMessage) => ({
        ...currentMessage,
        summary: data,
        _actionPending: null,
        actionError: "",
        _approved: decision === "approve",
        _denied: decision === "deny",
      }));
      if (typeof data?.run_id === "string") {
        onRunObserved?.(data.run_id);
      }
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
      updateMessageById(agentId, (currentMessage) => ({
        ...currentMessage,
        _actionPending: null,
        actionError: message,
      }));
    }
  }, [onRunObserved, updateMessageById]);

  const approveAction = useCallback((runId, approvalId, agentId) => {
    return resolveAction("approve", runId, approvalId, agentId);
  }, [resolveAction]);

  const denyAction = useCallback((runId, approvalId, agentId) => {
    return resolveAction("deny", runId, approvalId, agentId);
  }, [resolveAction]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitGoal();
    }
  };

  const handleExampleSelect = useCallback((goalText) => {
    setInput(goalText);
    inputRef.current?.focus();
  }, []);

  return (
    <div data-testid="hca-chat" className="assist-surface">
      <header className="assist-header">
        <div className="assist-headerGroup" style={S.headerLeft}>
          <span style={S.pulse} />
          <div className="assist-headerCopy">
            <span className="assist-headerTitle">Assist workspace</span>
            <span className="assist-headerSub">
              Start one goal, review the live summary, and pause only when an approval decision is needed.
            </span>
          </div>
        </div>
        <div className="assist-headerActions" style={S.headerRight}>
          <Chip>Bounded approval</Chip>
          <Chip>Replay-backed</Chip>
          <Chip>Memory-aware</Chip>
          <button
            className={`assist-memoryBtn${memPanelOpen ? " is-active" : ""}`}
            data-testid="memory-browser-btn"
            onClick={onToggleMemPanel}
            style={S.memBtn}
            type="button"
          >
            Quick memory
          </button>
        </div>
      </header>

      <div className="assist-feed">
        {messages.length === 0 && (
          <WelcomeBanner onSelectExample={handleExampleSelect} />
        )}

        {messages.map((msg) => {
          if (msg.type === "user") {
            return <UserBubble key={msg.id} goal={msg.content} />;
          }
          if (msg.type === "streaming") {
            return <StreamingCard key={msg.id} steps={msg.steps} goal={msg.goal} />;
          }
          if (msg.type === "agent") {
            return (
              <AgentCard
                key={msg.id}
                id={msg.id}
                data={msg.summary}
                steps={msg.steps || []}
                approved={msg._approved}
                denied={msg._denied}
                pendingAction={msg._actionPending}
                actionError={msg.actionError}
                onApprove={approveAction}
                onDeny={denyAction}
              />
            );
          }
          if (msg.type === "error") {
            return <ErrorCard key={msg.id} message={msg.content} />;
          }
          return null;
        })}

        <div ref={bottomRef} />
      </div>

      <section className="assist-composer">
        <div className="assist-composerIntro">
          <div className="assist-composerEyebrow">Goal composer</div>
          <div className="assist-composerTitle">
            Describe the outcome you want, not the tool steps.
          </div>
          <p className="assist-composerDescription">
            Hysight will stream a live summary, keep only the latest signals in front,
            and stop for approval before a side effect runs.
          </p>
        </div>

        <div className="assist-exampleList" aria-label="Example goals">
          {EXAMPLE_GOALS.map((example) => (
            <button
              key={example}
              className="assist-exampleButton"
              onClick={() => handleExampleSelect(example)}
              type="button"
            >
              {example}
            </button>
          ))}
        </div>

        <div className="assist-composerRow">
          <textarea
            ref={inputRef}
            className="assist-textarea"
            data-testid="goal-input"
            style={S.textarea}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe the result you want. The agent will show progress and pause if approval is needed."
            rows={3}
            disabled={loading}
          />
          <button
            className="assist-runBtn"
            data-testid="submit-goal-btn"
            style={{ ...S.runBtn, opacity: loading || !input.trim() ? 0.55 : 1 }}
            onClick={submitGoal}
            disabled={loading || !input.trim()}
            type="button"
          >
            {loading ? "Running..." : "Run goal"}
          </button>
        </div>

        <div className="assist-composerHint">
          Press Enter to submit. Use Shift+Enter when you want a multi-line goal.
        </div>
      </section>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function WelcomeBanner({ onSelectExample }) {
  return (
    <div className="assist-welcome">
      <div className="assist-welcomeIcon" style={S.welcomeIcon}>◎</div>
      <div className="assist-welcomeEyebrow">Assist workspace</div>
      <h1 className="assist-welcomeTitle">
        Ask for an outcome and keep the decision points obvious.
      </h1>
      <p className="assist-welcomeSub">
        The live run stays readable by default: recent signals first, approval state up front,
        and the dense reasoning details available only when you need them.
      </p>
      <p className="assist-tryLabel">Try one of these goals</p>
      <div className="assist-exampleList assist-exampleList--welcome">
        {EXAMPLE_GOALS.map((example) => (
          <button
            key={example}
            className="assist-exampleButton assist-exampleButton--welcome"
            onClick={() => onSelectExample(example)}
            type="button"
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}

function Chip({ children }) {
  return <span className="assist-chip">{children}</span>;
}

function UserBubble({ goal }) {
  return (
    <div data-testid="user-bubble" className="assist-userRow">
      <div className="assist-userBubble">{goal}</div>
    </div>
  );
}

function StreamingCard({ steps }) {
  const [traceOpen, setTraceOpen] = useState(false);
  const latestStep = steps[steps.length - 1] || null;
  const visibleSteps = traceOpen
    ? steps
    : steps.slice(-RECENT_STEP_PREVIEW_COUNT);

  return (
    <div data-testid="streaming-card" className="assist-agentRow">
      <div className="assist-liveCard" style={S.streamCard}>
        <div className="assist-liveHeader" style={S.streamHeader}>
          <div className="assist-liveHeaderTitle">
            <span style={S.spinner} />
            <div>
              <div className="assist-cardEyebrow">Live run</div>
              <span className="assist-liveTitle">The agent is working through the request.</span>
            </div>
          </div>
          <div className="assist-liveStatus">
            {latestStep ? formatSnakeLabel(latestStep.event_type) : "Starting"}
          </div>
        </div>
        <div className="assist-liveSummary">
          <p className="assist-liveSummaryText">{summarizeStreamingState(steps)}</p>
          {latestStep && (
            <div className="assist-liveSummaryMeta">
              Latest signal: {latestStep.label}
            </div>
          )}
        </div>

        {visibleSteps.length > 0 && (
          <div className="assist-tracePreview" style={S.traceList}>
            {visibleSteps.map((step, i) => (
              <TraceStep key={i} step={step} index={i} />
            ))}
          </div>
        )}

        {steps.length > RECENT_STEP_PREVIEW_COUNT && (
          <button
            className="assist-disclosureButton assist-disclosureButton--ghost"
            onClick={() => setTraceOpen((currentValue) => !currentValue)}
            type="button"
          >
            {traceOpen ? "Show fewer signals" : `Show full trace (${steps.length})`}
          </button>
        )}
      </div>
    </div>
  );
}

function TraceStep({ step, index }) {
  const cfg = STEP_ICONS[step.event_type] || { icon: "·", color: "#94a3b8" };
  return (
    <div
      style={{
        ...S.traceStep,
        animation: `fadeSlideIn 0.25s ease both`,
        animationDelay: `${index * 30}ms`,
      }}
    >
      <span style={{ ...S.traceIcon, color: cfg.color }}>{cfg.icon}</span>
      <div style={S.traceContent}>
        <span style={S.traceLabel}>{step.label}</span>
        {step.timestamp && (
          <span style={S.traceTime}>
            {new Date(step.timestamp).toISOString().slice(11, 19)}
          </span>
        )}
      </div>
    </div>
  );
}

function AgentCard({
  id,
  data,
  steps,
  approved,
  denied,
  pendingAction,
  actionError,
  onApprove,
  onDeny,
}) {
  const [traceOpen, setTraceOpen] = useState(false);
  const [memOpen,   setMemOpen]   = useState(false);
  const [reasoningOpen, setReasoningOpen] = useState(false);
  const [approvalOpen, setApprovalOpen] = useState(false);

  const state = data?.state || "completed";
  const stateMeta = STATE_META[state] || {
    label: state.toUpperCase(),
    color: "#374151",
    bg: "#f9fafb",
    border: "#d1d5db",
  };
  const plan = data?.plan || {};
  const perception = data?.perception || {};
  const critique = data?.critique || {};
  const workflow = data?.active_workflow || {};
  const workflowBudget = data?.workflow_budget || {};
  const workflowCheckpoint = data?.workflow_checkpoint || {};
  const workflowOutcome = data?.workflow_outcome || {};
  const workflowSteps = Array.isArray(data?.workflow_step_history)
    ? data.workflow_step_history
    : [];
  const actionTaken = data?.action_taken || {};
  const { request, decision, grant, consumption, binding } =
    getApprovalContext(data);
  const actionArgs = actionTaken.arguments || {};
  const result = data?.action_result || {};
  const memoryHits = Array.isArray(data?.memory_hits) ? data.memory_hits : [];
  const isAwaiting =
    state === "awaiting_approval" &&
    data?.approval_id &&
    !approved &&
    !denied;
  const hasApprovalContext =
    isAwaiting ||
    hasValue(data?.approval_id) ||
    hasValue(data?.approval) ||
    hasValue(data?.last_approval_decision);
  const buttonsDisabled = Boolean(pendingAction);
  const approvalTokens = approvalBindingTokens(binding);
  const summaryFacts = [
    {
      label: "Strategy",
      value: STRATEGY_LABELS[plan.strategy] || plan.strategy,
    },
    {
      label: "Action",
      value: actionTaken.kind || plan.action,
      mono: true,
    },
    {
      label: "Approval",
      value: formatApprovalStatus(data),
    },
    {
      label: "Workflow",
      value: workflow.workflow_class || formatWorkflowOutcome(workflowOutcome),
    },
    {
      label: "Context",
      value:
        memoryHits.length > 0
          ? `${memoryHits.length} memory hit${memoryHits.length === 1 ? "" : "s"}`
          : plan.memory_context_used
            ? "Retrieved context"
            : "No stored context",
    },
    {
      label: "Confidence",
      value: typeof plan.confidence === "number" ? formatScore(plan.confidence) : null,
    },
  ].filter((fact) => hasValue(fact.value));

  return (
    <div data-testid="agent-card" className="assist-agentRow">
      <div className="assist-resultCard" style={S.agentCard}>
        <div
          className="assist-statusBar"
          style={{ ...S.stateBar, background: stateMeta.bg, borderBottom: `1px solid ${stateMeta.border}` }}
        >
          <span style={{ ...S.stateBadge, color: stateMeta.color }}>
            {stateMeta.label}
          </span>
          {plan.strategy && (
            <span className="assist-statusMeta" style={S.strategyLabel}>
              {STRATEGY_LABELS[plan.strategy] || plan.strategy}
            </span>
          )}
        </div>

        <div className="assist-cardBody" style={S.cardBody}>
          <section className="assist-summaryPanel">
            <div className="assist-cardEyebrow">Run summary</div>
            <h3 className="assist-summaryTitle">
              {summarizeRunHeadline(data, actionTaken, plan)}
            </h3>
            <p className="assist-summaryText">
              {summarizeRunDescription(data, actionTaken, request, critique, result, workflowOutcome)}
            </p>
            <div className="assist-summaryGrid">
              {summaryFacts.map((fact) => (
                <SummaryFact
                  key={fact.label}
                  label={fact.label}
                  mono={fact.mono}
                  value={fact.value}
                />
              ))}
            </div>
          </section>

          {isAwaiting && (
            <section className="assist-approvalCard">
              <div className="assist-cardEyebrow">Approval required</div>
              <h4 className="assist-approvalTitle">
                {(request?.action_kind || actionTaken.kind || plan.action || "Action")} is waiting for your decision.
              </h4>
              <p className="assist-approvalText" style={S.approvalNote}>
                {request?.reason ||
                  `Review the selected action before ${actionTaken.kind || plan.action || "it"} executes.`}
              </p>

              {approvalTokens.length > 0 && <TokenList values={approvalTokens} />}

              {hasValue(actionArgs) && (
                <div style={S.jsonBlock}>
                  <span style={S.dataLabelBlock}>Pending arguments</span>
                  <pre style={S.jsonPreview}>
                    {formatObjectPreview(actionArgs)}
                  </pre>
                </div>
              )}

              <div className="assist-approvalActions" style={S.approvalBtns}>
                <button
                  className="assist-approveBtn"
                  data-testid="approve-btn"
                  style={{
                    ...S.approveBtn,
                    opacity: buttonsDisabled ? 0.6 : 1,
                    cursor: buttonsDisabled ? "not-allowed" : "pointer",
                  }}
                  type="button"
                  onClick={() => onApprove(data.run_id, data.approval_id, id)}
                  disabled={buttonsDisabled}
                >
                  {pendingAction === "approve" ? "Approving..." : "Approve"}
                </button>
                <button
                  className="assist-denyBtn"
                  data-testid="deny-btn"
                  style={{
                    ...S.denyBtn,
                    opacity: buttonsDisabled ? 0.6 : 1,
                    cursor: buttonsDisabled ? "not-allowed" : "pointer",
                  }}
                  type="button"
                  onClick={() => onDeny(data.run_id, data.approval_id, id)}
                  disabled={buttonsDisabled}
                >
                  {pendingAction === "deny" ? "Denying..." : "Deny"}
                </button>
              </div>

              {actionError && <div className="assist-inlineError" style={S.approvalError}>{actionError}</div>}
            </section>
          )}

          {result.status && !isAwaiting && (
            <section
              className={`assist-outcomeCard${result.status === "success" ? " assist-outcomeCard--success" : " assist-outcomeCard--danger"}`}
            >
              <div className="assist-cardEyebrow">Outcome</div>
              <h4 className="assist-outcomeTitle">
                {result.status === "success"
                  ? "The run completed and returned a result."
                  : "The run finished with an error state."}
              </h4>

              {result.outputs && (
                <div style={S.dataRow}>
                  <span style={S.dataLabel}>Output</span>
                  <MarkdownOutput text={_renderOutput(result.outputs)} />
                </div>
              )}

              {result.error && (
                <div className="assist-inlineError">{result.error}</div>
              )}

              {result.artifacts?.length > 0 && (
                <div className="assist-outcomeMeta">
                  Artifacts: {result.artifacts.join(", ")}
                </div>
              )}
            </section>
          )}

          {(plan.strategy ||
            hasValue(perception.intent_class) ||
            hasValue(critique.verdict) ||
            hasValue(workflow.workflow_class) ||
            workflowSteps.length > 0) && (
            <Collapsible
              label="Reasoning details"
              meta="Plan, perception, critique, and workflow"
              open={reasoningOpen}
              toggle={() => setReasoningOpen((value) => !value)}
            >
              {plan.strategy && (
                <Section label="PLAN">
                  <DataRow
                    label="Strategy"
                    value={STRATEGY_LABELS[plan.strategy] || plan.strategy}
                  />
                  <DataRow label="Action" value={plan.action || "—"} mono />
                  {plan.planning_mode && (
                    <DataRow label="Mode" value={plan.planning_mode} />
                  )}
                  <DataRow
                    label="Confidence"
                    value={formatScore(plan.confidence)}
                  />
                  {plan.rationale && <DataRow label="Rationale" value={plan.rationale} />}
                  {plan.fallback_reason && (
                    <DataRow label="Fallback" value={plan.fallback_reason} />
                  )}
                  {plan.memory_retrieval_status && (
                    <DataRow
                      label="Memory"
                      value={plan.memory_retrieval_status}
                      accent
                    />
                  )}
                  {plan.memory_retrieval_error && (
                    <DataRow
                      label="Memory error"
                      value={plan.memory_retrieval_error}
                      color="#dc2626"
                    />
                  )}
                  {plan.memory_context_used && (
                    <DataRow label="Context" value="Retrieved from retained memory" accent />
                  )}
                </Section>
              )}

              {hasValue(perception.intent_class) && (
                <Section label="PERCEPTION">
                  <DataRow label="Intent class" value={perception.intent_class} />
                  {perception.intent && (
                    <DataRow label="Intent" value={perception.intent} />
                  )}
                  {perception.perception_mode && (
                    <DataRow label="Mode" value={perception.perception_mode} />
                  )}
                  <DataRow
                    label="LLM attempted"
                    value={formatBoolean(perception.llm_attempted)}
                  />
                  {perception.fallback_reason && (
                    <DataRow label="Fallback" value={perception.fallback_reason} />
                  )}
                </Section>
              )}

              {(hasValue(critique.verdict) ||
                (Array.isArray(critique.issues) && critique.issues.length > 0)) && (
                <Section label="CRITIQUE">
                  {critique.verdict && (
                    <DataRow label="Verdict" value={critique.verdict} />
                  )}
                  <DataRow
                    label="Alignment"
                    value={formatScore(critique.alignment)}
                  />
                  <DataRow
                    label="Feasibility"
                    value={formatScore(critique.feasibility)}
                  />
                  <DataRow label="Safety" value={formatScore(critique.safety)} />
                  <DataRow
                    label="Confidence delta"
                    value={formatSignedNumber(critique.confidence_delta)}
                  />
                  <DataRow
                    label="LLM powered"
                    value={formatBoolean(critique.llm_powered)}
                  />
                  {critique.fallback_reason && (
                    <DataRow label="Fallback" value={critique.fallback_reason} />
                  )}
                  {critique.rationale && (
                    <DataRow label="Rationale" value={critique.rationale} />
                  )}
                  {Array.isArray(critique.issues) && critique.issues.length > 0 && (
                    <div style={S.issueBlock}>
                      <span style={S.dataLabelBlock}>Issues</span>
                      <ul style={S.issueList}>
                        {critique.issues.map((issue) => (
                          <li key={issue} style={S.issueItem}>
                            {issue}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </Section>
              )}

              {(hasValue(workflow.workflow_class) ||
                hasValue(workflowOutcome.reason) ||
                workflowSteps.length > 0) && (
                <Section label="WORKFLOW">
                  {workflow.workflow_class && (
                    <DataRow label="Class" value={workflow.workflow_class} />
                  )}
                  {workflow.strategy && (
                    <DataRow label="Strategy" value={workflow.strategy} />
                  )}
                  <DataRow
                    label="Budget"
                    value={formatWorkflowBudget(workflowBudget)}
                  />
                  <DataRow
                    label="Checkpoint"
                    value={formatWorkflowCheckpoint(workflowCheckpoint)}
                    mono
                  />
                  <DataRow
                    label="Outcome"
                    value={formatWorkflowOutcome(workflowOutcome)}
                  />
                  {workflowSteps.length > 0 && (
                    <div style={S.workflowStepBlock}>
                      <span style={S.dataLabelBlock}>Recent steps</span>
                      <div style={S.workflowStepList}>
                        {workflowSteps.slice(-3).map((step, index) => (
                          <div
                            key={step.step_id || step.action_id || `${index}`}
                            style={S.workflowStepItem}
                          >
                            <span style={S.workflowStepName}>
                              {step.step_key || step.tool_name || `step ${index + 1}`}
                            </span>
                            <span style={S.workflowStepMeta}>
                              {step.status || step.receipt_id || "—"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </Section>
              )}
            </Collapsible>
          )}

          {hasApprovalContext && !isAwaiting && (
            <Collapsible
              label="Approval details"
              meta="Binding, timestamps, and policy context"
              open={approvalOpen}
              toggle={() => setApprovalOpen((value) => !value)}
            >
              <Section label="APPROVAL">
                <DataRow label="Status" value={formatApprovalStatus(data)} />
                {request?.reason && <DataRow label="Reason" value={request.reason} />}
                {(request?.action_kind || actionTaken.kind) && (
                  <DataRow
                    label="Requested action"
                    value={request?.action_kind || actionTaken.kind}
                    mono
                  />
                )}
                {(request?.action_class || binding?.action_class) && (
                  <DataRow
                    label="Action class"
                    value={request?.action_class || binding?.action_class}
                  />
                )}
                {request?.requested_at && (
                  <DataRow
                    label="Requested at"
                    value={formatDateTime(request.requested_at)}
                  />
                )}
                {(decision?.decision || data?.last_approval_decision) && (
                  <DataRow
                    label="Decision"
                    value={decision?.decision || data?.last_approval_decision}
                  />
                )}
                {decision?.reason && (
                  <DataRow label="Decision reason" value={decision.reason} />
                )}
                {grant?.granted_at && (
                  <DataRow label="Granted at" value={formatDateTime(grant.granted_at)} />
                )}
                {consumption?.consumed_at && (
                  <DataRow label="Consumed at" value={formatDateTime(consumption.consumed_at)} />
                )}
                {binding?.tool_name && (
                  <DataRow label="Bound tool" value={binding.tool_name} mono />
                )}
                {binding?.target && (
                  <DataRow label="Bound target" value={binding.target} mono />
                )}
                {binding?.policy_fingerprint && (
                  <DataRow label="Policy fingerprint" value={binding.policy_fingerprint} mono />
                )}
                {binding?.action_fingerprint && (
                  <DataRow label="Action fingerprint" value={binding.action_fingerprint} mono />
                )}
                {hasValue(binding?.policy_snapshot) && (
                  <div style={S.jsonBlock}>
                    <span style={S.dataLabelBlock}>Policy snapshot</span>
                    <pre style={S.jsonPreview}>
                      {formatObjectPreview(binding.policy_snapshot)}
                    </pre>
                  </div>
                )}
              </Section>
            </Collapsible>
          )}

          {memoryHits.length > 0 && (
            <Collapsible
              label="Memory context"
              meta={`${memoryHits.length} hit${memoryHits.length > 1 ? "s" : ""}`}
              open={memOpen}
              toggle={() => setMemOpen((v) => !v)}
            >
              {memoryHits.map((h, i) => (
                <div key={i} style={S.memHit}>
                  <span style={S.memScore}>{h.score}</span>
                  <div style={S.memBody}>
                    <span style={S.memText}>{h.text}</span>
                    <span style={S.memMeta}>
                      {[
                        h.memory_type,
                        formatDateTime(h.stored_at),
                      ]
                        .filter(Boolean)
                        .join(" • ") || "memory hit"}
                    </span>
                  </div>
                </div>
              ))}
            </Collapsible>
          )}

          {/* Pipeline trace (completed) */}
          {steps.length > 0 && (
            <Collapsible
              label="Full pipeline trace"
              meta={`${steps.length} signal${steps.length === 1 ? "" : "s"}`}
              open={traceOpen}
              toggle={() => setTraceOpen((v) => !v)}
            >
              <div style={S.traceList}>
                {steps.map((step, i) => (
                  <TraceStep key={i} step={step} index={i} />
                ))}
              </div>
            </Collapsible>
          )}

          <div className="assist-runId" style={S.runIdLine}>
            run_id: <span style={S.runIdVal}>{data?.run_id}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ErrorCard({ message }) {
  return (
    <div data-testid="error-bubble" className="assist-agentRow">
      <div className="assist-errorCard" style={S.errorCard}>{message}</div>
    </div>
  );
}

function Section({ label, children }) {
  return (
    <div style={S.section}>
      <div style={S.sectionLabel}>{label}</div>
      {children}
    </div>
  );
}

function DataRow({ label, value, mono, color, accent }) {
  return (
    <div style={S.dataRow}>
      <span style={S.dataLabel}>{label}</span>
      <span
        style={{
          ...S.dataValue,
          ...(mono   ? S.mono   : {}),
          ...(color  ? { color }             : {}),
          ...(accent ? { color: "#0891b2" }  : {}),
        }}
      >
        {value}
      </span>
    </div>
  );
}

function SummaryFact({ label, value, mono = false }) {
  return (
    <div className="assist-summaryFact">
      <div className="assist-summaryFactLabel">{label}</div>
      <div className={`assist-summaryFactValue${mono ? " is-mono" : ""}`}>
        {value}
      </div>
    </div>
  );
}

function TokenList({ values }) {
  return (
    <div className="assist-tokenList">
      {values.map((value) => (
        <span key={value} className="assist-token">
          {value}
        </span>
      ))}
    </div>
  );
}

function Collapsible({ label, meta, open, toggle, children }) {
  return (
    <div className="assist-collapsible" style={S.section}>
      <button className="assist-collapsibleBtn" onClick={toggle} type="button">
        <div>
          <span className="assist-collapsibleLabel">{label}</span>
          {meta ? <span className="assist-collapsibleMeta">{meta}</span> : null}
        </div>
        <span className="assist-collapsibleIcon">{open ? "Hide" : "Show"}</span>
      </button>
      {open && <div className="assist-collapsibleBody">{children}</div>}
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function MarkdownOutput({ text }) {
  return (
    <div style={S.mdOutput}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p:      ({ children }) => <p style={S.mdP}>{children}</p>,
          strong: ({ children }) => <strong style={S.mdStrong}>{children}</strong>,
          em:     ({ children }) => <em style={S.mdEm}>{children}</em>,
          ol:     ({ children }) => <ol style={S.mdOl}>{children}</ol>,
          ul:     ({ children }) => <ul style={S.mdUl}>{children}</ul>,
          li:     ({ children }) => <li style={S.mdLi}>{children}</li>,
          h1:     ({ children }) => <h1 style={S.mdH}>{children}</h1>,
          h2:     ({ children }) => <h2 style={{ ...S.mdH, fontSize: 17 }}>{children}</h2>,
          h3:     ({ children }) => <h3 style={{ ...S.mdH, fontSize: 16 }}>{children}</h3>,
          code:   ({ inline, children }) =>
            inline
              ? <code style={S.mdInlineCode}>{children}</code>
              : <pre style={S.mdPre}><code style={S.mdCode}>{children}</code></pre>,
          blockquote: ({ children }) => <blockquote style={S.mdBlockquote}>{children}</blockquote>,
          hr:     () => <hr style={S.mdHr} />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

function _renderOutput(outputs) {
  if (!outputs) return "";
  if (typeof outputs === "string") return outputs.replace(/\\n/g, "\n");
  if (typeof outputs === "object") {
    // If echo action: {"echo": "...text..."} → show text
    const val = outputs.echo || outputs.text || outputs.result || outputs.output;
    if (val) return String(val).replace(/\\n/g, "\n");
    return JSON.stringify(outputs, null, 2);
  }
  return String(outputs);
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

function getApprovalContext(data) {
  const approval =
    data?.approval && typeof data.approval === "object" ? data.approval : null;

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

  return { request, decision, grant, consumption, binding };
}

function formatApprovalStatus(data) {
  if (!data) {
    return "—";
  }

  if (data.approval?.status) {
    if (data.approval.status === "pending" && data.approval_id) {
      return `pending (${data.approval_id})`;
    }

    return data.approval.status;
  }

  if (data.last_approval_decision) {
    return data.last_approval_decision;
  }

  if (data.approval_id) {
    return `pending (${data.approval_id})`;
  }

  return "—";
}

function formatBoolean(value) {
  return value ? "Yes" : "No";
}

function formatScore(value) {
  if (typeof value !== "number") return "—";
  return value.toFixed(2);
}

function formatSignedNumber(value) {
  if (typeof value !== "number") return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

function formatWorkflowBudget(budget) {
  if (!hasValue(budget)) return "—";

  const consumedSteps = budget.consumed_steps ?? 0;
  const maxSteps = budget.max_steps ?? "—";
  return `${consumedSteps}/${maxSteps} steps`;
}

function formatWorkflowCheckpoint(checkpoint) {
  if (!hasValue(checkpoint)) return "—";

  const parts = [
    checkpoint.current_step_id,
    typeof checkpoint.current_step_index === "number"
      ? `index ${checkpoint.current_step_index}`
      : null,
  ].filter(Boolean);

  return parts.join(" • ") || "—";
}

function formatWorkflowOutcome(outcome) {
  if (!hasValue(outcome)) return "—";

  return [outcome.terminal_event, outcome.reason]
    .filter(Boolean)
    .join(" • ") || "—";
}

function formatDateTime(value) {
  if (!value) return "";

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

function formatObjectPreview(value) {
  try {
    const serialized = JSON.stringify(value || {}, null, 2);
    return serialized.length > 520
      ? `${serialized.slice(0, 520)}...`
      : serialized;
  } catch {
    return "{}";
  }
}

function formatSnakeLabel(value) {
  if (!value) return "—";

  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function approvalBindingTokens(binding) {
  if (!binding || typeof binding !== "object") {
    return [];
  }

  return [
    binding.tool_name ? `tool ${binding.tool_name}` : null,
    binding.target ? `target ${binding.target}` : null,
    binding.policy_fingerprint ? `policy ${binding.policy_fingerprint}` : null,
    binding.action_fingerprint ? `action ${binding.action_fingerprint}` : null,
  ].filter(Boolean);
}

function summarizeStreamingState(steps) {
  if (!steps.length) {
    return "Waiting for the first live signal from the run.";
  }

  const latestStep = steps[steps.length - 1];

  switch (latestStep.event_type) {
    case "approval_requested":
      return "The run has enough context to pause for approval.";
    case "execution_started":
      return "The approved action is now executing.";
    case "execution_finished":
      return "Execution finished and the result is being recorded.";
    case "run_completed":
      return "The run completed and the summary is ready below.";
    case "run_failed":
      return "The run reported a failure. Review the summary card for details.";
    default:
      return latestStep.label || `${steps.length} live signal${steps.length === 1 ? "" : "s"} received.`;
  }
}

function summarizeRunHeadline(data, actionTaken, plan) {
  const actionLabel = actionTaken.kind || plan.action || "The selected action";

  switch (data?.state) {
    case "awaiting_approval":
      return `${actionLabel} is ready for operator approval.`;
    case "completed":
      return "The run completed and returned a result.";
    case "failed":
      return "The run failed before it could finish.";
    case "halted":
      return "The run was halted before execution completed.";
    default:
      return `${actionLabel} is progressing through the workflow.`;
  }
}

function summarizeRunDescription(data, actionTaken, request, critique, result, workflowOutcome) {
  const actionLabel = actionTaken.kind || data?.plan?.action || "action";

  switch (data?.state) {
    case "awaiting_approval":
      return (
        request?.reason ||
        `${actionLabel} is staged and waiting for a human approval decision before it executes.`
      );
    case "completed":
      return (
        workflowOutcome?.reason ||
        result?.status ||
        `${actionLabel} completed successfully and replay data is available.`
      );
    case "failed":
      return (
        result?.error ||
        workflowOutcome?.reason ||
        critique?.issues?.[0] ||
        `${actionLabel} did not complete. Review the reasoning and trace details.`
      );
    case "halted":
      return (
        workflowOutcome?.reason ||
        critique?.issues?.[0] ||
        `${actionLabel} stopped before completion.`
      );
    default:
      return `${actionLabel} is still in progress. The latest live signals are shown above.`;
  }
}

function showRunToast(summary) {
  if (!summary || typeof summary !== "object") {
    return;
  }

  if (summary.state === "awaiting_approval") {
    toast({
      title: "Approval required",
      description: `${summary.action_taken?.kind || "Action"} is waiting for sign-off.`,
    });
    return;
  }

  if (summary.state === "completed") {
    toast({
      title: "Run completed",
      description: summary.goal || summary.run_id || "The run completed successfully.",
    });
    return;
  }

  if (summary.state === "failed" || summary.state === "halted") {
    toast({
      title: summary.state === "failed" ? "Run failed" : "Run halted",
      description:
        summary.action_result?.error ||
        summary.workflow_outcome?.reason ||
        summary.goal ||
        "The run did not complete successfully.",
      variant: "destructive",
    });
  }
}

// ── Styles (white theme, bigger text) ────────────────────────────────────────

const C = {
  bg:       "#f8fafc",
  white:    "#ffffff",
  border:   "#e2e8f0",
  text:     "#0f172a",
  muted:    "#64748b",
  blue:     "#2563eb",
  cyan:     "#0891b2",
  green:    "#059669",
  amber:    "#d97706",
  red:      "#dc2626",
  violet:   "#7c3aed",
  indigo:   "#6366f1",
  mono:     "#1e3a5f",
};

const S = {
  container: {
    display:       "flex",
    flexDirection: "column",
    height:        "100vh",
    background:    C.bg,
    color:         C.text,
    fontFamily:    "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    overflow:      "hidden",
  },

  // ── Header ──────────────────────────────────────────────────────────────────
  header: {
    display:        "flex",
    alignItems:     "center",
    justifyContent: "space-between",
    padding:        "14px 28px",
    background:     C.white,
    borderBottom:   `1px solid ${C.border}`,
    boxShadow:      "0 1px 3px rgba(0,0,0,0.06)",
    flexShrink:     0,
  },
  headerLeft: { display: "flex", alignItems: "center", gap: 12 },
  pulse: {
    display:      "inline-block",
    width:        10,
    height:       10,
    borderRadius: "50%",
    background:   C.indigo,
    boxShadow:    `0 0 0 3px rgba(99,102,241,0.2)`,
    animation:    "pulse 2s infinite",
  },
  headerTitle: {
    fontSize:      20,
    fontWeight:    800,
    color:         C.indigo,
    letterSpacing: "-0.02em",
  },
  headerSub: {
    fontSize: 14,
    color:    C.muted,
  },
  headerRight: { display: "flex", gap: 8 },
  chip: {
    fontSize:     12,
    padding:      "3px 10px",
    borderRadius: 20,
    border:       `1px solid ${C.border}`,
    color:        C.muted,
    background:   C.bg,
    fontWeight:   500,
  },
  memBtn: {
    fontSize:     13,
    padding:      "4px 14px",
    borderRadius: 20,
    border:       `1px solid ${C.border}`,
    cursor:       "pointer",
    fontWeight:   600,
    transition:   "all 0.15s",
    letterSpacing: "0.01em",
  },

  // ── Feed ────────────────────────────────────────────────────────────────────
  feed: {
    flex:          1,
    overflowY:     "auto",
    padding:       "32px 20px",
    display:       "flex",
    flexDirection: "column",
    gap:           20,
    maxWidth:      900,
    width:         "100%",
    margin:        "0 auto",
    boxSizing:     "border-box",
  },

  // ── Welcome ─────────────────────────────────────────────────────────────────
  welcome: {
    textAlign:  "center",
    padding:    "60px 20px 40px",
    maxWidth:   640,
    margin:     "0 auto",
  },
  welcomeIcon:  { fontSize: 40, color: C.indigo, marginBottom: 16 },
  welcomeTitle: { fontSize: 32, fontWeight: 800, color: C.text, marginBottom: 12, letterSpacing: "-0.03em" },
  welcomeSub:   { fontSize: 17, color: C.muted, lineHeight: 1.7, marginBottom: 28 },
  tryLabel:     { fontSize: 13, color: C.muted, marginBottom: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" },
  chips:        { display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "center" },
  exChip: {
    fontSize:     13,
    padding:      "6px 12px",
    background:   C.white,
    border:       `1px solid ${C.border}`,
    borderRadius: 8,
    color:        C.muted,
    cursor:       "default",
    boxShadow:    "0 1px 2px rgba(0,0,0,0.04)",
  },

  // ── User bubble ──────────────────────────────────────────────────────────────
  userRow:    { display: "flex", justifyContent: "flex-end" },
  userBubble: {
    maxWidth:     "72%",
    padding:      "12px 18px",
    background:   "#eff6ff",
    border:       "1px solid #bfdbfe",
    borderRadius: "16px 16px 4px 16px",
    fontSize:     16,
    lineHeight:   1.6,
    color:        "#1e40af",
    fontWeight:   500,
  },

  // ── Agent row wrapper ────────────────────────────────────────────────────────
  agentRow: { display: "flex", justifyContent: "flex-start" },

  // ── Streaming card ───────────────────────────────────────────────────────────
  streamCard: {
    width:        "100%",
    background:   C.white,
    border:       `1px solid ${C.border}`,
    borderRadius: 12,
    overflow:     "hidden",
    boxShadow:    "0 1px 4px rgba(0,0,0,0.06)",
  },
  streamHeader: {
    display:       "flex",
    alignItems:    "center",
    gap:           10,
    padding:       "14px 18px",
    borderBottom:  `1px solid ${C.border}`,
    background:    "#fafbfc",
  },
  spinner: {
    display:         "inline-block",
    width:           14,
    height:          14,
    borderRadius:    "50%",
    border:          `2px solid ${C.indigo}`,
    borderTopColor:  "transparent",
    animation:       "spin 0.8s linear infinite",
    flexShrink:      0,
  },
  streamTitle: { fontSize: 15, fontWeight: 600, color: C.text },

  // ── Trace list ────────────────────────────────────────────────────────────────
  traceList: { padding: "10px 18px", display: "flex", flexDirection: "column", gap: 6 },
  traceStep: {
    display:    "flex",
    alignItems: "flex-start",
    gap:        10,
    padding:    "4px 0",
  },
  traceIcon:    { fontSize: 16, width: 20, textAlign: "center", flexShrink: 0, paddingTop: 1 },
  traceContent: { display: "flex", alignItems: "baseline", gap: 12, flex: 1 },
  traceLabel:   { fontSize: 14, color: C.text, fontWeight: 500 },
  traceTime:    { fontSize: 12, color: C.muted, fontFamily: "'JetBrains Mono', monospace" },

  // ── Agent card ────────────────────────────────────────────────────────────────
  agentCard: {
    width:        "100%",
    background:   C.white,
    border:       `1px solid ${C.border}`,
    borderRadius: 12,
    overflow:     "hidden",
    boxShadow:    "0 1px 4px rgba(0,0,0,0.06)",
  },
  stateBar: {
    display:    "flex",
    alignItems: "center",
    gap:        12,
    padding:    "10px 18px",
  },
  stateBadge: {
    fontSize:      11,
    fontWeight:    800,
    letterSpacing: "0.1em",
  },
  strategyLabel: { fontSize: 13, color: C.muted },
  cardBody: {
    padding:       "16px 18px",
    display:       "flex",
    flexDirection: "column",
    gap:           14,
  },

  // ── Section ────────────────────────────────────────────────────────────────────
  section: {
    borderTop: `1px solid ${C.border}`,
    paddingTop: 12,
  },
  sectionLabel: {
    fontSize:      11,
    color:         C.muted,
    letterSpacing: "0.1em",
    fontWeight:    700,
    textTransform: "uppercase",
    marginBottom:  8,
    display:       "block",
  },

  // ── Data row ─────────────────────────────────────────────────────────────────
  dataRow:   { display: "flex", gap: 14, marginBottom: 6, flexWrap: "wrap" },
  dataLabel: { fontSize: 13, color: C.muted, minWidth: 78, flexShrink: 0, paddingTop: 2 },
  dataValue: { fontSize: 15, color: C.text, flex: 1, lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word" },
  mono:      { fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: C.mono },
  dataLabelBlock: {
    fontSize: 13,
    color: C.muted,
    marginBottom: 6,
    display: "block",
  },
  jsonBlock: {
    marginBottom: 8,
  },
  jsonPreview: {
    margin: 0,
    padding: "10px 12px",
    borderRadius: 10,
    background: "#f8fafc",
    border: `1px solid ${C.border}`,
    color: C.mono,
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 12,
    lineHeight: 1.55,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  issueBlock: {
    marginBottom: 8,
  },
  issueList: {
    margin: 0,
    paddingLeft: 18,
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  issueItem: {
    fontSize: 14,
    color: C.text,
    lineHeight: 1.55,
  },

  // ── Memory hits ───────────────────────────────────────────────────────────────
  memHit:   { display: "flex", gap: 10, marginBottom: 5 },
  memScore: { fontSize: 12, color: C.cyan, minWidth: 38, paddingTop: 2, fontFamily: "monospace" },
  memBody: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    flex: 1,
  },
  memText:  { fontSize: 14, color: C.muted, flex: 1, lineHeight: 1.5 },
  memMeta: {
    fontSize: 12,
    color: "#94a3b8",
    lineHeight: 1.4,
  },

  // ── Approval ─────────────────────────────────────────────────────────────────
  approvalNote: { fontSize: 15, color: C.text, lineHeight: 1.6, marginBottom: 14 },
  approvalBtns: { display: "flex", gap: 10 },
  approvalError: { marginTop: 10, fontSize: 13, color: C.red, lineHeight: 1.5 },
  approveBtn: {
    padding:      "9px 22px",
    borderRadius: 8,
    border:       "none",
    cursor:       "pointer",
    background:   "#d1fae5",
    color:        C.green,
    fontSize:     14,
    fontWeight:   700,
    transition:   "background 0.15s",
  },
  denyBtn: {
    padding:      "9px 22px",
    borderRadius: 8,
    border:       "none",
    cursor:       "pointer",
    background:   "#fee2e2",
    color:        C.red,
    fontSize:     14,
    fontWeight:   700,
    transition:   "background 0.15s",
  },

  // ── Collapsible button ────────────────────────────────────────────────────────
  collapsibleBtn: {
    display:        "flex",
    alignItems:     "center",
    justifyContent: "space-between",
    width:          "100%",
    background:     "none",
    border:         "none",
    cursor:         "pointer",
    padding:        0,
    textAlign:      "left",
    marginBottom:   0,
  },

  // ── Run ID ────────────────────────────────────────────────────────────────────
  runIdLine: { fontSize: 12, color: "#cbd5e1", marginTop: 4 },
  runIdVal:  { fontFamily: "monospace", color: "#94a3b8" },
  workflowStepBlock: {
    marginBottom: 8,
  },
  workflowStepList: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  workflowStepItem: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    padding: "8px 10px",
    borderRadius: 10,
    border: `1px solid ${C.border}`,
    background: "#f8fafc",
  },
  workflowStepName: {
    fontSize: 13,
    color: C.text,
    fontWeight: 600,
  },
  workflowStepMeta: {
    fontSize: 12,
    color: C.muted,
    textAlign: "right",
  },

  // ── Markdown output ───────────────────────────────────────────────────────────
  mdOutput: { flex: 1, minWidth: 0 },
  mdP:      { fontSize: 15, color: C.text, lineHeight: 1.7, marginBottom: 10 },
  mdStrong: { fontWeight: 700, color: C.text },
  mdEm:     { fontStyle: "italic", color: C.muted },
  mdH:      { fontSize: 18, fontWeight: 700, color: C.text, marginBottom: 8, marginTop: 12 },
  mdOl:     { paddingLeft: 22, marginBottom: 10 },
  mdUl:     { paddingLeft: 22, marginBottom: 10 },
  mdLi:     { fontSize: 15, color: C.text, lineHeight: 1.7, marginBottom: 4 },
  mdInlineCode: {
    background:   "#f1f5f9",
    border:       "1px solid #e2e8f0",
    borderRadius: 4,
    padding:      "1px 5px",
    fontFamily:   "'JetBrains Mono', monospace",
    fontSize:     13,
    color:        C.mono,
  },
  mdPre: {
    background:   "#f8fafc",
    border:       "1px solid #e2e8f0",
    borderRadius: 8,
    padding:      "12px 16px",
    overflowX:    "auto",
    marginBottom: 10,
  },
  mdCode: {
    fontFamily: "'JetBrains Mono', monospace",
    fontSize:   13,
    color:      C.mono,
    background: "none",
    border:     "none",
    padding:    0,
  },
  mdBlockquote: {
    borderLeft:  `3px solid ${C.indigo}`,
    paddingLeft: 14,
    marginLeft:  0,
    color:       C.muted,
    fontSize:    15,
    lineHeight:  1.7,
    marginBottom: 10,
  },
  mdHr: { border: "none", borderTop: `1px solid ${C.border}`, margin: "12px 0" },

  // ── Error card ────────────────────────────────────────────────────────────────
  errorCard: {
    padding:      "12px 16px",
    background:   "#fef2f2",
    border:       "1px solid #fca5a5",
    borderRadius: 10,
    fontSize:     15,
    color:        C.red,
  },

  // ── Input bar ─────────────────────────────────────────────────────────────────
  inputBar: {
    display:      "flex",
    gap:          12,
    padding:      "14px 20px",
    background:   C.white,
    borderTop:    `1px solid ${C.border}`,
    boxShadow:    "0 -1px 3px rgba(0,0,0,0.04)",
    flexShrink:   0,
    maxWidth:     900,
    width:        "100%",
    margin:       "0 auto",
    boxSizing:    "border-box",
  },
  textarea: {
    flex:        1,
    resize:      "none",
    background:  C.bg,
    border:      `1.5px solid ${C.border}`,
    borderRadius: 10,
    color:       C.text,
    fontSize:    16,
    padding:     "11px 16px",
    fontFamily:  "inherit",
    outline:     "none",
    lineHeight:  1.5,
    transition:  "border-color 0.15s",
  },
  runBtn: {
    padding:      "0 24px",
    background:   C.indigo,
    border:       "none",
    borderRadius: 10,
    color:        "#fff",
    fontSize:     14,
    fontWeight:   700,
    letterSpacing: "0.06em",
    cursor:       "pointer",
    transition:   "opacity 0.15s, background 0.15s",
    flexShrink:   0,
  },
};

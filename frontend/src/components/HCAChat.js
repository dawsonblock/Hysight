import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  decideRunApproval,
  getResponseErrorMessage,
  streamRun,
  toErrorMessage,
} from "@/lib/api";

// Events worth showing in the live trace (filter out internal plumbing)
const VISIBLE_EVENTS = new Set([
  "run_created", "module_proposed", "meta_assessed", "action_selected",
  "approval_requested", "execution_started", "execution_finished",
  "memory_written", "run_completed", "run_failed",
]);

// ── Pipeline step config ──────────────────────────────────────────────────────

const STEP_ICONS = {
  run_created:        { icon: "◎", color: "#6366f1" },
  module_proposed:    { icon: "◈", color: "#0ea5e9" },
  meta_assessed:      { icon: "◇", color: "#8b5cf6" },
  action_scored:      { icon: "◆", color: "#8b5cf6" },
  action_selected:    { icon: "▷", color: "#f59e0b" },
  approval_requested: { icon: "⊛", color: "#ec4899" },
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
            updateMessageById(agentId, (currentMessage) => ({
              ...currentMessage,
              type: "agent",
              summary: data,
              _actionPending: null,
              actionError: "",
            }));
          } else if (eventType === "error") {
            updateMessageById(agentId, (currentMessage) => ({
              ...currentMessage,
              type: "error",
              content: data.label,
            }));
          }
        }
      }
    } catch (error) {
      updateMessageById(agentId, (currentMessage) => ({
        ...currentMessage,
        type: "error",
        content: toErrorMessage(error, "Request failed."),
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
      updateMessageById(agentId, (currentMessage) => ({
        ...currentMessage,
        _actionPending: null,
        actionError: toErrorMessage(
          error,
          decision === "approve" ? "Approval failed." : "Deny failed."
        ),
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

  return (
    <div data-testid="hca-chat" style={S.container}>
      {/* Header */}
      <header style={S.header}>
        <div style={S.headerLeft}>
          <span style={S.pulse} />
          <span style={S.headerTitle}>HCA</span>
          <span style={S.headerSub}>Hybrid Cognitive Agent</span>
        </div>
        <div style={S.headerRight}>
          <Chip>Claude Sonnet 4.5</Chip>
          <Chip>Gemini Flash</Chip>
          <Chip>MemVid</Chip>
          <button
            data-testid="memory-browser-btn"
            onClick={onToggleMemPanel}
            style={{
              ...S.memBtn,
              background: memPanelOpen ? "#ede9fe" : "#f8fafc",
              color:      memPanelOpen ? "#6d28d9" : "#64748b",
              borderColor: memPanelOpen ? "#c4b5fd" : "#e2e8f0",
            }}
          >
            Memory
          </button>
        </div>
      </header>

      {/* Message feed */}
      <div style={S.feed}>
        {messages.length === 0 && <WelcomeBanner />}

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

      {/* Input bar */}
      <div style={S.inputBar}>
        <textarea
          data-testid="goal-input"
          style={S.textarea}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter a goal for the agent…  (Enter to run)"
          rows={1}
          disabled={loading}
        />
        <button
          data-testid="submit-goal-btn"
          style={{ ...S.runBtn, opacity: loading || !input.trim() ? 0.4 : 1 }}
          onClick={submitGoal}
          disabled={loading || !input.trim()}
        >
          {loading ? "…" : "RUN"}
        </button>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function WelcomeBanner() {
  const examples = [
    "Remember that the API key expires on March 1st",
    "Find what I said about the database migration",
    "Write a brief project status summary",
    "Hello, what can you do?",
  ];
  return (
    <div style={S.welcome}>
      <div style={S.welcomeIcon}>◎</div>
      <h1 style={S.welcomeTitle}>Cognitive Agent Console</h1>
      <p style={S.welcomeSub}>
        Give the agent a goal. It plans, reasons, and acts — every step of the pipeline visible in real time.
      </p>
      <p style={S.tryLabel}>Try one of these:</p>
      <div style={S.chips}>
        {examples.map((ex) => (
          <code key={ex} style={S.exChip}>{ex}</code>
        ))}
      </div>
    </div>
  );
}

function Chip({ children }) {
  return <span style={S.chip}>{children}</span>;
}

function UserBubble({ goal }) {
  return (
    <div data-testid="user-bubble" style={S.userRow}>
      <div style={S.userBubble}>{goal}</div>
    </div>
  );
}

function StreamingCard({ steps, goal }) {
  return (
    <div data-testid="streaming-card" style={S.agentRow}>
      <div style={S.streamCard}>
        <div style={S.streamHeader}>
          <span style={S.spinner} />
          <span style={S.streamTitle}>Agent is thinking…</span>
        </div>
        {steps.length > 0 && (
          <div style={S.traceList}>
            {steps.map((step, i) => (
              <TraceStep key={i} step={step} index={i} />
            ))}
          </div>
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

  const state     = data?.state || "completed";
  const stateMeta = STATE_META[state] || { label: state.toUpperCase(), color: "#374151", bg: "#f9fafb", border: "#d1d5db" };
  const plan      = data?.plan || {};
  const result    = data?.action_result || {};
  const isAwaiting = state === "awaiting_approval" && data?.approval_id && !approved && !denied;
  const buttonsDisabled = Boolean(pendingAction);

  return (
    <div data-testid="agent-card" style={S.agentRow}>
      <div style={S.agentCard}>
        {/* State badge bar */}
        <div style={{ ...S.stateBar, background: stateMeta.bg, borderBottom: `1px solid ${stateMeta.border}` }}>
          <span style={{ ...S.stateBadge, color: stateMeta.color }}>
            {stateMeta.label}
          </span>
          {plan.strategy && (
            <span style={S.strategyLabel}>
              {STRATEGY_LABELS[plan.strategy] || plan.strategy}
            </span>
          )}
        </div>

        <div style={S.cardBody}>
          {/* Plan section */}
          {plan.strategy && (
            <Section label="PLAN">
              <DataRow label="Strategy"  value={STRATEGY_LABELS[plan.strategy] || plan.strategy} />
              <DataRow label="Action"    value={plan.action || "—"} mono />
              {plan.rationale && <DataRow label="Rationale" value={plan.rationale} />}
              {plan.memory_context_used && (
                <DataRow label="Context" value="Retrieved from MemVid memory store" accent />
              )}
            </Section>
          )}

          {/* Execution result */}
          {result.status && (
            <Section label="RESULT">
              <DataRow
                label="Status"
                value={result.status}
                color={result.status === "success" ? "#059669" : "#dc2626"}
              />
              {result.outputs && (
                <div style={S.dataRow}>
                  <span style={S.dataLabel}>Output</span>
                  <MarkdownOutput text={_renderOutput(result.outputs)} />
                </div>
              )}
              {result.error && <DataRow label="Error" value={result.error} color="#dc2626" />}
              {result.artifacts?.length > 0 && (
                <DataRow label="Artifacts" value={result.artifacts.join(", ")} mono />
              )}
            </Section>
          )}

          {/* Approval gate */}
          {isAwaiting && (
            <Section label="APPROVAL REQUIRED">
              <p style={S.approvalNote}>
                The agent wants to run{" "}
                <strong style={{ color: "#d97706" }}>{data.action_taken?.kind}</strong>.
                This action needs your sign-off before it executes.
              </p>
              <div style={S.approvalBtns}>
                <button
                  data-testid="approve-btn"
                  style={{
                    ...S.approveBtn,
                    opacity: buttonsDisabled ? 0.6 : 1,
                    cursor: buttonsDisabled ? "not-allowed" : "pointer",
                  }}
                  onClick={() => onApprove(data.run_id, data.approval_id, id)}
                  disabled={buttonsDisabled}
                >
                  {pendingAction === "approve" ? "Approving..." : "Approve"}
                </button>
                <button
                  data-testid="deny-btn"
                  style={{
                    ...S.denyBtn,
                    opacity: buttonsDisabled ? 0.6 : 1,
                    cursor: buttonsDisabled ? "not-allowed" : "pointer",
                  }}
                  onClick={() => onDeny(data.run_id, data.approval_id, id)}
                  disabled={buttonsDisabled}
                >
                  {pendingAction === "deny" ? "Denying..." : "Deny"}
                </button>
              </div>
              {actionError && <div style={S.approvalError}>{actionError}</div>}
            </Section>
          )}

          {/* Memory hits */}
          {data?.memory_hits?.length > 0 && (
            <Collapsible
              label={`MEMORY CONTEXT  (${data.memory_hits.length} hit${data.memory_hits.length > 1 ? "s" : ""})`}
              open={memOpen}
              toggle={() => setMemOpen((v) => !v)}
            >
              {data.memory_hits.map((h, i) => (
                <div key={i} style={S.memHit}>
                  <span style={S.memScore}>{h.score}</span>
                  <span style={S.memText}>{h.text}</span>
                </div>
              ))}
            </Collapsible>
          )}

          {/* Pipeline trace (completed) */}
          {steps.length > 0 && (
            <Collapsible
              label={`PIPELINE TRACE  (${steps.length} step${steps.length > 1 ? "s" : ""})`}
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

          <div style={S.runIdLine}>
            run_id: <span style={S.runIdVal}>{data?.run_id}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ErrorCard({ message }) {
  return (
    <div data-testid="error-bubble" style={S.agentRow}>
      <div style={S.errorCard}>{message}</div>
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

function Collapsible({ label, open, toggle, children }) {
  return (
    <div style={S.section}>
      <button style={S.collapsibleBtn} onClick={toggle}>
        <span style={S.sectionLabel}>{label}</span>
        <span style={{ color: "#94a3b8", fontSize: 11 }}>{open ? "▲" : "▼"}</span>
      </button>
      {open && <div style={{ marginTop: 8 }}>{children}</div>}
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

  // ── Memory hits ───────────────────────────────────────────────────────────────
  memHit:   { display: "flex", gap: 10, marginBottom: 5 },
  memScore: { fontSize: 12, color: C.cyan, minWidth: 38, paddingTop: 2, fontFamily: "monospace" },
  memText:  { fontSize: 14, color: C.muted, flex: 1, lineHeight: 1.5 },

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

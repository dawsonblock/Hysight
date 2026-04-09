import { useState, useRef, useEffect, useCallback } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATE_META = {
  completed:         { label: "COMPLETED",         color: "#34d399", bg: "rgba(52,211,153,0.12)"  },
  awaiting_approval: { label: "AWAITING APPROVAL", color: "#a78bfa", bg: "rgba(167,139,250,0.12)" },
  failed:            { label: "FAILED",             color: "#f87171", bg: "rgba(248,113,113,0.12)" },
  halted:            { label: "HALTED",             color: "#fb923c", bg: "rgba(251,146,60,0.12)"  },
  executing:         { label: "EXECUTING",          color: "#22d3ee", bg: "rgba(34,211,238,0.12)"  },
  proposing:         { label: "PLANNING",           color: "#22d3ee", bg: "rgba(34,211,238,0.12)"  },
};

const STRATEGY_LABELS = {
  single_action_dispatch:        "Direct Dispatch",
  memory_persistence_strategy:   "Memory Write",
  information_retrieval_strategy:"Memory Retrieval",
  artifact_authoring_strategy:   "Artifact Creation",
};

export default function HCAChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const submitGoal = useCallback(async () => {
    const goal = input.trim();
    if (!goal || loading) return;
    setInput("");
    setLoading(true);

    const userMsg = { type: "user", content: goal, id: `u-${Date.now()}` };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const { data } = await axios.post(`${API}/hca/run`, { goal });
      setMessages((prev) => [
        ...prev,
        { type: "agent", content: data, id: `a-${Date.now()}` },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          type: "error",
          content: err?.response?.data?.detail || err.message,
          id: `e-${Date.now()}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading]);

  const approveAction = useCallback(async (runId, approvalId) => {
    try {
      const { data } = await axios.post(`${API}/hca/run/${runId}/approve`, {
        approval_id: approvalId,
      });
      setMessages((prev) =>
        prev.map((m) =>
          m.type === "agent" && m.content?.run_id === runId
            ? { ...m, content: { ...m.content, ...data, _approved: true } }
            : m
        )
      );
    } catch (err) {
      console.error("Approval failed", err);
    }
  }, []);

  const denyAction = useCallback(async (runId, approvalId) => {
    try {
      const { data } = await axios.post(`${API}/hca/run/${runId}/deny`, {
        approval_id: approvalId,
      });
      setMessages((prev) =>
        prev.map((m) =>
          m.type === "agent" && m.content?.run_id === runId
            ? { ...m, content: { ...m.content, ...data, _denied: true } }
            : m
        )
      );
    } catch (err) {
      console.error("Deny failed", err);
    }
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitGoal();
    }
  };

  return (
    <div data-testid="hca-chat" style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.headerDot} />
          <span style={styles.headerTitle}>HCA</span>
          <span style={styles.headerSub}>Hybrid Cognitive Agent</span>
        </div>
        <div style={styles.headerRight}>
          <span style={styles.badge}>Claude Sonnet 4.5</span>
          <span style={styles.badge}>Gemini Flash</span>
          <span style={styles.badge}>MemVid</span>
        </div>
      </div>

      {/* Messages */}
      <div style={styles.messages}>
        {messages.length === 0 && <WelcomeBanner />}
        {messages.map((msg) => {
          if (msg.type === "user") return <UserBubble key={msg.id} goal={msg.content} />;
          if (msg.type === "agent")
            return (
              <AgentCard
                key={msg.id}
                data={msg.content}
                onApprove={approveAction}
                onDeny={denyAction}
              />
            );
          return <ErrorBubble key={msg.id} message={msg.content} />;
        })}
        {loading && <ThinkingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={styles.inputArea}>
        <textarea
          data-testid="goal-input"
          style={styles.textarea}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter a goal for the agent…  (⏎ to run)"
          rows={1}
          disabled={loading}
        />
        <button
          data-testid="submit-goal-btn"
          style={{ ...styles.runBtn, opacity: loading || !input.trim() ? 0.45 : 1 }}
          onClick={submitGoal}
          disabled={loading || !input.trim()}
        >
          {loading ? "▶" : "RUN"}
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
    <div style={styles.welcome}>
      <div style={styles.welcomeTitle}>Cognitive Agent Console</div>
      <div style={styles.welcomeSub}>
        Give the agent a goal. It will plan, reason, and act — all traces visible below.
      </div>
      <div style={styles.examplesLabel}>Try:</div>
      <div style={styles.examplesList}>
        {examples.map((ex) => (
          <code key={ex} style={styles.exampleChip}>{ex}</code>
        ))}
      </div>
    </div>
  );
}

function UserBubble({ goal }) {
  return (
    <div data-testid="user-bubble" style={styles.userBubbleWrap}>
      <div style={styles.userBubble}>{goal}</div>
    </div>
  );
}

function AgentCard({ data, onApprove, onDeny }) {
  const [expanded, setExpanded] = useState(true);
  const [traceOpen, setTraceOpen] = useState(false);
  const [memOpen, setMemOpen] = useState(false);
  const stateMeta = STATE_META[data.state] || { label: data.state, color: "#94a3b8", bg: "rgba(148,163,184,0.1)" };
  const isAwaiting = data.state === "awaiting_approval" && data.approval_id && !data._approved && !data._denied;
  const result = data.action_result || {};
  const plan   = data.plan || {};

  return (
    <div data-testid="agent-card" style={styles.agentCardWrap}>
      <div style={styles.agentCard}>
        {/* Card header */}
        <div style={styles.agentCardHeader} onClick={() => setExpanded((v) => !v)}>
          <div style={styles.agentCardHeaderLeft}>
            <span style={{ ...styles.stateBadge, color: stateMeta.color, background: stateMeta.bg }}>
              {stateMeta.label}
            </span>
            {plan.strategy && (
              <span style={styles.strategyTag}>
                {STRATEGY_LABELS[plan.strategy] || plan.strategy}
              </span>
            )}
          </div>
          <span style={styles.collapseArrow}>{expanded ? "▲" : "▼"}</span>
        </div>

        {expanded && (
          <div style={styles.agentCardBody}>
            {/* Plan section */}
            {plan.strategy && (
              <Section label="PLAN">
                <Row label="Strategy"  value={STRATEGY_LABELS[plan.strategy] || plan.strategy} />
                <Row label="Action"    value={plan.action || "—"} mono />
                {plan.rationale && <Row label="Rationale" value={plan.rationale} />}
                {plan.memory_context_used && (
                  <Row label="Memory"  value="Context retrieved from MemVid store" accent />
                )}
              </Section>
            )}

            {/* Action result */}
            {result.status && (
              <Section label="EXECUTION">
                <Row
                  label="Status"
                  value={result.status}
                  color={result.status === "success" ? "#34d399" : "#f87171"}
                />
                {result.outputs && (
                  <Row label="Output" value={JSON.stringify(result.outputs)} mono />
                )}
                {result.error && <Row label="Error" value={result.error} color="#f87171" />}
                {result.artifacts?.length > 0 && (
                  <Row label="Artifacts" value={result.artifacts.join(", ")} mono />
                )}
              </Section>
            )}

            {/* Approval flow */}
            {isAwaiting && (
              <Section label="APPROVAL REQUIRED">
                <div style={styles.approvalNote}>
                  The agent wants to execute <strong style={{ color: "#f59e0b" }}>{data.action_taken?.kind}</strong>.
                  This action requires your approval before it runs.
                </div>
                <div style={styles.approvalBtns}>
                  <button
                    data-testid="approve-btn"
                    style={styles.approveBtn}
                    onClick={() => onApprove(data.run_id, data.approval_id)}
                  >
                    Approve
                  </button>
                  <button
                    data-testid="deny-btn"
                    style={styles.denyBtn}
                    onClick={() => onDeny(data.run_id, data.approval_id)}
                  >
                    Deny
                  </button>
                </div>
              </Section>
            )}

            {/* Memory hits */}
            {data.memory_hits?.length > 0 && (
              <Collapsible
                label={`MEMORY CONTEXT  (${data.memory_hits.length} hit${data.memory_hits.length > 1 ? "s" : ""})`}
                open={memOpen}
                toggle={() => setMemOpen((v) => !v)}
              >
                {data.memory_hits.map((h, i) => (
                  <div key={i} style={styles.memHit}>
                    <span style={styles.memScore}>{h.score}</span>
                    <span style={styles.memText}>{h.text}</span>
                  </div>
                ))}
              </Collapsible>
            )}

            {/* Event trace */}
            {data.key_events?.length > 0 && (
              <Collapsible
                label={`TRACE  (${data.event_count} events)`}
                open={traceOpen}
                toggle={() => setTraceOpen((v) => !v)}
              >
                {data.key_events.map((ev, i) => (
                  <div key={i} style={styles.traceRow}>
                    <span style={styles.traceTime}>
                      {ev.timestamp ? new Date(ev.timestamp).toISOString().slice(11, 19) : "—"}
                    </span>
                    <span style={styles.traceActor}>{ev.actor || "—"}</span>
                    <span style={styles.traceText}>{ev.summary}</span>
                  </div>
                ))}
              </Collapsible>
            )}

            <div style={styles.runIdLine}>run_id: <span style={styles.runIdVal}>{data.run_id}</span></div>
          </div>
        )}
      </div>
    </div>
  );
}

function ErrorBubble({ message }) {
  return (
    <div data-testid="error-bubble" style={styles.errorBubble}>
      {message}
    </div>
  );
}

function ThinkingIndicator() {
  return (
    <div data-testid="thinking-indicator" style={styles.thinking}>
      <span style={styles.thinkDot} />
      <span style={{ ...styles.thinkDot, animationDelay: "0.15s" }} />
      <span style={{ ...styles.thinkDot, animationDelay: "0.3s" }} />
      <span style={styles.thinkText}>Agent is planning…</span>
    </div>
  );
}

function Section({ label, children }) {
  return (
    <div style={styles.section}>
      <div style={styles.sectionLabel}>{label}</div>
      {children}
    </div>
  );
}

function Row({ label, value, mono, color, accent }) {
  return (
    <div style={styles.row}>
      <span style={styles.rowLabel}>{label}</span>
      <span
        style={{
          ...styles.rowValue,
          ...(mono  ? styles.mono  : {}),
          ...(color ? { color }    : {}),
          ...(accent? { color: "#22d3ee" } : {}),
        }}
      >
        {value}
      </span>
    </div>
  );
}

function Collapsible({ label, open, toggle, children }) {
  return (
    <div style={styles.section}>
      <div style={{ ...styles.sectionLabel, cursor: "pointer", userSelect: "none" }} onClick={toggle}>
        {label}  <span style={{ opacity: 0.5 }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && <div>{children}</div>}
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const C = {
  bg:       "#080810",
  surface:  "#0f0f1a",
  border:   "#1a1a2e",
  text:     "#e2e8f0",
  muted:    "#475569",
  cyan:     "#22d3ee",
  amber:    "#f59e0b",
  green:    "#34d399",
  violet:   "#a78bfa",
  red:      "#f87171",
};

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    background: C.bg,
    color: C.text,
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
    overflow: "hidden",
  },

  // Header
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "12px 24px",
    background: C.surface,
    borderBottom: `1px solid ${C.border}`,
    flexShrink: 0,
  },
  headerLeft: { display: "flex", alignItems: "center", gap: 12 },
  headerDot: {
    display: "inline-block", width: 8, height: 8,
    borderRadius: "50%", background: C.cyan,
    boxShadow: `0 0 8px ${C.cyan}`,
    animation: "pulse 2s infinite",
  },
  headerTitle: { fontSize: 16, fontWeight: 700, letterSpacing: "0.1em", color: C.cyan },
  headerSub:   { fontSize: 11, color: C.muted, letterSpacing: "0.08em" },
  headerRight: { display: "flex", gap: 8 },
  badge: {
    fontSize: 10, padding: "2px 8px", borderRadius: 4,
    border: `1px solid ${C.border}`, color: C.muted, letterSpacing: "0.05em",
  },

  // Messages
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "24px 16px",
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },

  // Welcome
  welcome: {
    margin: "40px auto",
    maxWidth: 600,
    textAlign: "center",
  },
  welcomeTitle: { fontSize: 22, fontWeight: 700, color: C.cyan, marginBottom: 8 },
  welcomeSub:   { fontSize: 13, color: C.muted, marginBottom: 24, lineHeight: 1.6 },
  examplesLabel:{ fontSize: 11, color: C.muted, marginBottom: 8, letterSpacing: "0.1em" },
  examplesList: { display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center" },
  exampleChip: {
    fontSize: 11, padding: "4px 10px",
    background: "rgba(34,211,238,0.07)",
    border: `1px solid rgba(34,211,238,0.2)`,
    borderRadius: 6, color: "#94a3b8", cursor: "default",
  },

  // User bubble
  userBubbleWrap: { display: "flex", justifyContent: "flex-end" },
  userBubble: {
    maxWidth: "70%",
    padding: "10px 16px",
    background: "rgba(245,158,11,0.12)",
    border: `1px solid rgba(245,158,11,0.3)`,
    borderRadius: "12px 12px 2px 12px",
    fontSize: 13,
    lineHeight: 1.6,
    color: "#fde68a",
  },

  // Agent card
  agentCardWrap: { display: "flex", justifyContent: "flex-start", maxWidth: "92%" },
  agentCard: {
    width: "100%",
    background: C.surface,
    border: `1px solid ${C.border}`,
    borderRadius: 8,
    overflow: "hidden",
  },
  agentCardHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "10px 16px",
    cursor: "pointer",
    borderBottom: `1px solid ${C.border}`,
    background: "rgba(255,255,255,0.02)",
  },
  agentCardHeaderLeft: { display: "flex", alignItems: "center", gap: 10 },
  stateBadge: {
    fontSize: 10, fontWeight: 700, letterSpacing: "0.1em",
    padding: "2px 8px", borderRadius: 4,
  },
  strategyTag: {
    fontSize: 11, color: C.muted, letterSpacing: "0.05em",
  },
  collapseArrow: { fontSize: 10, color: C.muted },
  agentCardBody: { padding: "12px 16px", display: "flex", flexDirection: "column", gap: 12 },

  // Section
  section: {
    borderTop: `1px solid ${C.border}`,
    paddingTop: 10,
  },
  sectionLabel: {
    fontSize: 10, color: C.muted, letterSpacing: "0.12em",
    marginBottom: 6, fontWeight: 700,
  },

  // Row
  row: { display: "flex", gap: 12, marginBottom: 4, flexWrap: "wrap" },
  rowLabel: { fontSize: 11, color: C.muted, minWidth: 80, flexShrink: 0 },
  rowValue: { fontSize: 12, color: C.text, flex: 1 },
  mono: { fontFamily: "inherit", color: "#86efac" },

  // Memory hits
  memHit: { display: "flex", gap: 10, marginBottom: 4 },
  memScore: { fontSize: 10, color: C.cyan, minWidth: 36, paddingTop: 1 },
  memText:  { fontSize: 11, color: "#94a3b8", flex: 1, lineHeight: 1.5 },

  // Trace
  traceRow: { display: "flex", gap: 10, marginBottom: 3 },
  traceTime:  { fontSize: 10, color: C.muted, minWidth: 64 },
  traceActor: { fontSize: 10, color: C.violet, minWidth: 80 },
  traceText:  { fontSize: 11, color: "#94a3b8", flex: 1 },

  // Approval
  approvalNote: { fontSize: 12, color: "#cbd5e1", lineHeight: 1.6, marginBottom: 12 },
  approvalBtns: { display: "flex", gap: 10 },
  approveBtn: {
    padding: "7px 20px", borderRadius: 6, border: "none", cursor: "pointer",
    background: "rgba(52,211,153,0.15)", color: C.green,
    fontSize: 12, fontWeight: 700, letterSpacing: "0.06em",
    transition: "background 0.15s",
  },
  denyBtn: {
    padding: "7px 20px", borderRadius: 6, border: "none", cursor: "pointer",
    background: "rgba(248,113,113,0.12)", color: C.red,
    fontSize: 12, fontWeight: 700, letterSpacing: "0.06em",
    transition: "background 0.15s",
  },

  // Run ID
  runIdLine: { fontSize: 10, color: C.muted, marginTop: 4 },
  runIdVal:  { color: "#4b5563", letterSpacing: "0.03em" },

  // Error bubble
  errorBubble: {
    padding: "8px 14px",
    background: "rgba(248,113,113,0.1)",
    border: `1px solid rgba(248,113,113,0.25)`,
    borderRadius: 6,
    fontSize: 12, color: C.red,
  },

  // Thinking
  thinking: {
    display: "flex", alignItems: "center", gap: 6, padding: "8px 4px",
  },
  thinkDot: {
    display: "inline-block", width: 6, height: 6,
    borderRadius: "50%", background: C.cyan, opacity: 0.4,
    animation: "blink 1s infinite",
  },
  thinkText: { fontSize: 11, color: C.muted, marginLeft: 4 },

  // Input area
  inputArea: {
    display: "flex",
    gap: 10,
    padding: "12px 16px",
    background: C.surface,
    borderTop: `1px solid ${C.border}`,
    flexShrink: 0,
  },
  textarea: {
    flex: 1,
    resize: "none",
    background: C.bg,
    border: `1px solid ${C.border}`,
    borderRadius: 6,
    color: C.text,
    fontSize: 13,
    padding: "10px 14px",
    fontFamily: "inherit",
    outline: "none",
    lineHeight: 1.5,
    transition: "border-color 0.15s",
  },
  runBtn: {
    padding: "0 20px",
    background: "rgba(34,211,238,0.1)",
    border: `1px solid rgba(34,211,238,0.35)`,
    borderRadius: 6,
    color: C.cyan,
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: "0.1em",
    cursor: "pointer",
    transition: "background 0.15s",
    flexShrink: 0,
  },
};

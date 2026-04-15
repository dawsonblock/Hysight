import { useState, useEffect, useCallback, useRef } from "react";
import {
  deleteMemoryRecord,
  listMemories,
  toErrorMessage,
} from "@/lib/api";
import { toast } from "@/hooks/use-toast";

const TYPE_META = {
  episode:    { color: "#6366f1", bg: "#eef2ff", label: "Episode"   },
  fact:       { color: "#0891b2", bg: "#ecfeff", label: "Fact"      },
  trace:      { color: "#94a3b8", bg: "#f8fafc", label: "Trace"     },
  preference: { color: "#d97706", bg: "#fffbeb", label: "Preference"},
  goalstate:  { color: "#059669", bg: "#ecfdf5", label: "Goal"      },
  procedure:  { color: "#7c3aed", bg: "#f5f3ff", label: "Procedure" },
};
const DEFAULT_TYPE = { color: "#64748b", bg: "#f1f5f9", label: "?" };

const ALL_TYPES = ["episode", "fact", "trace", "preference", "goalstate", "procedure"];
const PAGE_SIZE = 20;
const SEARCH_LIMIT = 200;

export default function MemoryBrowser({
  open,
  onClose,
  variant = "modal",
  title = "Memory Store",
  subtitle,
}) {
  const [records, setRecords]     = useState([]);
  const [total, setTotal]         = useState(0);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState("");
  const [search, setSearch]       = useState("");
  const [typeFilter, setTypeFilter] = useState(null);
  const [page, setPage]           = useState(0);
  const [deleting, setDeleting]   = useState(null);
  const [selectedMemoryId, setSelectedMemoryId] = useState(null);
  const [searchLimited, setSearchLimited] = useState(false);
  const searchRef = useRef(null);
  const isEmbedded = variant === "embedded";

  const fetchRecords = useCallback(async (queryText, type, currentPage) => {
    setLoading(true);
    setError("");
    setSearchLimited(false);

    try {
      const isSearchMode = queryText.trim().length > 0;

      const data = await listMemories({
        memoryType: type,
        limit: isSearchMode ? SEARCH_LIMIT : PAGE_SIZE,
        offset: isSearchMode ? 0 : currentPage * PAGE_SIZE,
      });

      if (!Array.isArray(data?.records) || typeof data?.total !== "number") {
        throw new Error("Memory list response was invalid.");
      }

      if (isSearchMode) {
        const normalizedQuery = queryText.trim().toLowerCase();
        const filteredRecords = data.records.filter((record) => {
          const text = typeof record.text === "string"
            ? record.text.toLowerCase()
            : "";
          const memoryType = typeof record.memory_type === "string"
            ? record.memory_type.toLowerCase()
            : "";

          return (
            text.includes(normalizedQuery) ||
            memoryType.includes(normalizedQuery)
          );
        });

        const start = currentPage * PAGE_SIZE;
        setRecords(filteredRecords.slice(start, start + PAGE_SIZE));
        setTotal(filteredRecords.length);
        setSearchLimited(data.total > SEARCH_LIMIT);
        return;
      }

      setRecords(data.records);
      setTotal(data.total);
    } catch (error) {
      setRecords([]);
      setTotal(0);
      setError(toErrorMessage(error, "Unable to load memories."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }

    fetchRecords(search, typeFilter, page);
  }, [open, search, typeFilter, page, fetchRecords]);

  useEffect(() => {
    if (open) {
      searchRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    if (!open || isEmbedded) {
      return undefined;
    }

    const handleEscape = (event) => {
      if (event.key === "Escape") {
        onClose?.();
      }
    };

    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("keydown", handleEscape);
    };
  }, [isEmbedded, onClose, open]);

  useEffect(() => {
    if (records.length === 0) {
      if (selectedMemoryId !== null) {
        setSelectedMemoryId(null);
      }
      return;
    }

    if (!records.some((record) => record.memory_id === selectedMemoryId)) {
      setSelectedMemoryId(records[0].memory_id);
    }
  }, [records, selectedMemoryId]);

  const handleSearch = (event) => {
    setSearch(event.target.value);
    setPage(0);
  };

  const handleTypeFilter = (type) => {
    setTypeFilter((currentType) => (currentType === type ? null : type));
    setPage(0);
  };

  const handleDelete = async (memoryId) => {
    setDeleting(memoryId);
    try {
      setError("");
      const data = await deleteMemoryRecord(memoryId);

      if (!data?.deleted || data.memory_id !== memoryId) {
        throw new Error("Memory delete did not complete.");
      }

      toast({
        title: "Memory deleted",
        description: "The selected record was removed from the memory store.",
      });

      if (page > 0 && records.length === 1) {
        setPage((currentPage) => currentPage - 1);
      } else {
        await fetchRecords(search, typeFilter, page);
      }
    } catch (error) {
      const message = toErrorMessage(error, "Delete failed.");
      toast({
        title: "Delete failed",
        description: message,
        variant: "destructive",
      });
      setError(message);
    } finally {
      setDeleting(null);
    }
  };

  const isSearchMode = search.trim().length > 0;
  const hasFilters = isSearchMode || Boolean(typeFilter);
  const selectedRecord =
    records.find((record) => record.memory_id === selectedMemoryId) || null;
  const computedSubtitle =
    subtitle ||
    `${total} ${isSearchMode ? "matching " : ""}record${
      total !== 1 ? "s" : ""
    }${isSearchMode ? "" : " total"}`;

  if (!open) return null;

  return (
    <>
      {!isEmbedded && (
        <div
          data-testid="memory-backdrop"
          style={S.backdrop}
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <aside
        aria-label="Memory store"
        aria-modal={isEmbedded ? undefined : "true"}
        data-testid="memory-browser"
        role={isEmbedded ? "region" : "dialog"}
        style={isEmbedded ? S.embeddedPanel : S.panel}
      >
        {/* Header */}
        <div style={S.panelHeader}>
          <div>
            <div style={S.panelTitle}>{title}</div>
            <div style={S.panelSub}>{computedSubtitle}</div>
          </div>
          <div style={S.headerActions}>
            {hasFilters && (
              <button
                type="button"
                style={S.secondaryBtn}
                onClick={() => {
                  setSearch("");
                  setTypeFilter(null);
                  setPage(0);
                }}
              >
                Clear filters
              </button>
            )}
            {!isEmbedded && (
              <button
                data-testid="close-memory-btn"
                style={S.closeBtn}
                onClick={onClose}
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Search */}
        <div style={S.searchRow}>
          <input
            data-testid="memory-search-input"
            aria-label="Search memories"
            ref={searchRef}
            style={S.searchInput}
            placeholder="Search memories…"
            value={search}
            onChange={handleSearch}
          />
          {search && (
            <button
              style={S.clearBtn}
              onClick={() => {
                setSearch("");
                setPage(0);
              }}
            >
              ✕
            </button>
          )}
        </div>

        {/* Type filters */}
        <div style={S.filterRow}>
          {ALL_TYPES.map((type) => {
            const meta = TYPE_META[type] || DEFAULT_TYPE;
            const active = typeFilter === type;
            return (
              <button
                key={type}
                data-testid={`type-filter-${type}`}
                onClick={() => handleTypeFilter(type)}
                style={{
                  ...S.filterChip,
                  background:  active ? meta.bg  : "#f8fafc",
                  color:       active ? meta.color : "#94a3b8",
                  borderColor: active ? meta.color : "#e2e8f0",
                  fontWeight:  active ? 700 : 400,
                }}
              >
                {meta.label}
              </button>
            );
          })}
        </div>

        {isSearchMode && searchLimited && (
          <div style={S.notice}>
            Text search scans the newest {SEARCH_LIMIT} memories for the current filter.
          </div>
        )}

        <div style={S.selectionSummary}>
          <span>
            {records.length} loaded on this page
            {typeFilter ? ` • ${TYPE_META[typeFilter]?.label || typeFilter}` : ""}
          </span>
          {selectedRecord && (
            <span>
              Selected {TYPE_META[selectedRecord.memory_type]?.label || selectedRecord.memory_type || "memory"}
            </span>
          )}
        </div>

        {/* Records list */}
        <div style={S.list}>
          {loading && <div style={S.loadingMsg}>Loading…</div>}

          {!loading && error && <div style={S.errorMsg}>{error}</div>}

          {!loading && !error && records.length === 0 && (
            <div style={S.emptyMsg}>
              {search || typeFilter ? "No matching memories." : "No memories stored yet."}
            </div>
          )}

          {records.map((rec) => (
            <MemoryRow
              key={rec.memory_id}
              rec={rec}
              deleting={deleting === rec.memory_id}
              selected={rec.memory_id === selectedMemoryId}
              onSelect={() => setSelectedMemoryId(rec.memory_id)}
              onDelete={() => handleDelete(rec.memory_id)}
            />
          ))}
        </div>

        {selectedRecord && !loading && !error && (
          <section style={S.detailPane}>
            <div style={S.detailHeader}>
              <div>
                <div style={S.detailEyebrow}>Selected Record</div>
                <div style={S.detailTitle}>
                  {TYPE_META[selectedRecord.memory_type]?.label || selectedRecord.memory_type || "Memory"}
                </div>
              </div>
              <div style={S.detailTimestamp}>
                {selectedRecord.stored_at
                  ? new Date(selectedRecord.stored_at).toLocaleString()
                  : "Unknown time"}
              </div>
            </div>

            <div style={S.detailGrid}>
              <DetailField label="Memory ID" value={selectedRecord.memory_id} mono />
              <DetailField
                label="Run ID"
                value={selectedRecord.run_id || "—"}
                mono
              />
              <DetailField
                label="Type"
                value={TYPE_META[selectedRecord.memory_type]?.label || selectedRecord.memory_type || "—"}
              />
              <DetailField
                label="Stored"
                value={selectedRecord.stored_at
                  ? new Date(selectedRecord.stored_at).toLocaleString()
                  : "—"}
              />
            </div>

            <div style={S.detailBody}>
              {selectedRecord.text}
            </div>
          </section>
        )}

        {/* Pagination */}
        {total > PAGE_SIZE && (
          <div style={S.pagination}>
            <button
              style={{ ...S.pageBtn, opacity: page === 0 ? 0.3 : 1 }}
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
            >
              ← Prev
            </button>
            <span style={S.pageInfo}>
              {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
            </span>
            <button
              style={{ ...S.pageBtn, opacity: (page + 1) * PAGE_SIZE >= total ? 0.3 : 1 }}
              disabled={(page + 1) * PAGE_SIZE >= total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next →
            </button>
          </div>
        )}
      </aside>
    </>
  );
}

// ── Memory row ────────────────────────────────────────────────────────────────

function MemoryRow({ rec, deleting, selected, onDelete, onSelect }) {
  const meta = TYPE_META[rec.memory_type] || DEFAULT_TYPE;

  const storedAt = rec.stored_at
    ? new Date(rec.stored_at).toLocaleString(undefined, {
        month: "short", day: "numeric",
        hour:  "2-digit", minute: "2-digit",
      })
    : "—";

  return (
    <div
      data-testid="memory-row"
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      role="button"
      style={{
        ...S.row,
        ...(selected ? S.rowSelected : null),
        opacity: deleting ? 0.4 : 1,
      }}
      tabIndex={0}
    >
      <div style={S.rowTop}>
        <div style={S.rowLeft}>
          <span style={{ ...S.typeBadge, color: meta.color, background: meta.bg }}>
            {meta.label}
          </span>
          <span style={S.rowText}>
            {rec.text?.length > 88 ? rec.text.slice(0, 88) + "…" : rec.text}
          </span>
        </div>
        <div style={S.rowRight}>
          <span style={S.rowTime}>{storedAt}</span>
          <button
            data-testid="delete-memory-btn"
            style={S.deleteBtn}
            disabled={deleting}
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            title="Delete"
          >
            {deleting ? "…" : "✕"}
          </button>
        </div>
      </div>
      <div style={S.rowMeta}>
        {rec.run_id ? (
          <>
            run_id: <span style={S.rowMetaVal}>{rec.run_id}</span>
          </>
        ) : (
          "No run linkage"
        )}
      </div>
    </div>
  );
}

function DetailField({ label, value, mono = false }) {
  return (
    <div style={S.detailField}>
      <div style={S.detailFieldLabel}>{label}</div>
      <div style={{ ...S.detailFieldValue, ...(mono ? S.detailFieldMono : null) }}>
        {value}
      </div>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const S = {
  backdrop: {
    position:   "fixed",
    inset:      0,
    background: "rgba(15,23,42,0.2)",
    zIndex:     40,
    backdropFilter: "blur(2px)",
  },
  panel: {
    position:      "fixed",
    top:           0,
    right:         0,
    bottom:        0,
    width:         "min(420px, 100vw)",
    background:    "#ffffff",
    borderLeft:    "1px solid #e2e8f0",
    boxShadow:     "-4px 0 24px rgba(15,23,42,0.1)",
    zIndex:        50,
    display:       "flex",
    flexDirection: "column",
    overflow:      "hidden",
    animation:     "slideInRight 0.2s ease",
  },
  embeddedPanel: {
    position:      "relative",
    inset:         "auto",
    width:         "100%",
    height:        "100%",
    background:    "rgba(255,255,255,0.92)",
    border:        "1px solid #dbe4ee",
    borderRadius:  24,
    boxShadow:     "0 18px 36px rgba(15,23,42,0.08)",
    display:       "flex",
    flexDirection: "column",
    overflow:      "hidden",
  },

  panelHeader: {
    display:        "flex",
    alignItems:     "center",
    justifyContent: "space-between",
    padding:        "18px 20px",
    borderBottom:   "1px solid #e2e8f0",
    flexShrink:     0,
  },
  headerActions: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  panelTitle: { fontSize: 18, fontWeight: 700, color: "#0f172a" },
  panelSub:   { fontSize: 13, color: "#64748b", marginTop: 2 },
  secondaryBtn: {
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    background: "#f8fafc",
    color: "#475569",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 700,
    padding: "7px 10px",
  },
  closeBtn: {
    width:        32,
    height:       32,
    border:       "1px solid #e2e8f0",
    borderRadius: 8,
    background:   "#f8fafc",
    color:        "#64748b",
    cursor:       "pointer",
    fontSize:     14,
    display:      "flex",
    alignItems:   "center",
    justifyContent: "center",
  },

  searchRow: {
    display:   "flex",
    alignItems: "center",
    padding:   "12px 16px",
    gap:       8,
    borderBottom: "1px solid #f1f5f9",
    flexShrink: 0,
  },
  searchInput: {
    flex:        1,
    border:      "1.5px solid #e2e8f0",
    borderRadius: 8,
    padding:     "8px 12px",
    fontSize:    14,
    color:       "#0f172a",
    background:  "#f8fafc",
    outline:     "none",
    fontFamily:  "inherit",
  },
  clearBtn: {
    border:      "none",
    background:  "none",
    color:       "#94a3b8",
    cursor:      "pointer",
    fontSize:    14,
    padding:     "0 4px",
  },

  filterRow: {
    display:    "flex",
    flexWrap:   "wrap",
    gap:        6,
    padding:    "10px 16px",
    borderBottom: "1px solid #f1f5f9",
    flexShrink: 0,
  },
  notice: {
    padding: "10px 16px 0",
    fontSize: 12,
    lineHeight: 1.5,
    color: "#64748b",
  },
  selectionSummary: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    padding: "12px 16px 0",
    fontSize: 12,
    color: "#64748b",
    lineHeight: 1.5,
  },
  filterChip: {
    fontSize:     11,
    padding:      "3px 10px",
    borderRadius: 20,
    border:       "1px solid",
    cursor:       "pointer",
    fontFamily:   "inherit",
    transition:   "all 0.12s",
  },

  list: {
    flex:      1,
    overflowY: "auto",
    padding:   "8px 0",
  },
  errorMsg: {
    margin: "12px 16px 0",
    padding: "12px 14px",
    borderRadius: 8,
    border: "1px solid #fca5a5",
    background: "#fef2f2",
    color: "#b91c1c",
    fontSize: 14,
    lineHeight: 1.5,
  },
  loadingMsg: { padding: "24px 20px", textAlign: "center", fontSize: 14, color: "#94a3b8" },
  emptyMsg:   { padding: "40px 20px", textAlign: "center", fontSize: 15, color: "#94a3b8" },

  row: {
    borderBottom: "1px solid #f8fafc",
    padding:      "10px 16px",
    transition:   "background 0.12s, opacity 0.2s",
    cursor:       "pointer",
  },
  rowSelected: {
    background: "#f8fafc",
    boxShadow: "inset 3px 0 0 #6366f1",
  },
  rowTop: {
    display:        "flex",
    alignItems:     "flex-start",
    justifyContent: "space-between",
    gap:            10,
  },
  rowLeft:  { display: "flex", alignItems: "flex-start", gap: 8, flex: 1, minWidth: 0 },
  rowRight: { display: "flex", alignItems: "center", gap: 8, flexShrink: 0 },
  typeBadge: {
    fontSize:     10,
    fontWeight:   700,
    letterSpacing: "0.06em",
    padding:      "2px 7px",
    borderRadius: 20,
    flexShrink:   0,
    marginTop:    2,
  },
  rowText: {
    fontSize:   14,
    color:      "#334155",
    lineHeight: 1.5,
    flex:       1,
    wordBreak:  "break-word",
  },
  rowTime:   { fontSize: 11, color: "#94a3b8", whiteSpace: "nowrap" },
  deleteBtn: {
    width:        24,
    height:       24,
    border:       "none",
    background:   "none",
    color:        "#cbd5e1",
    cursor:       "pointer",
    fontSize:     13,
    borderRadius: 6,
    display:      "flex",
    alignItems:   "center",
    justifyContent: "center",
    transition:   "color 0.12s, background 0.12s",
    flexShrink:   0,
  },
  rowMeta:    { fontSize: 11, color: "#94a3b8", paddingTop: 4, paddingLeft: 56 },
  rowMetaVal: { fontFamily: "monospace", color: "#cbd5e1" },
  detailPane: {
    borderTop: "1px solid #e2e8f0",
    background: "#f8fafc",
    padding: "14px 16px 16px",
    display: "flex",
    flexDirection: "column",
    gap: 12,
    flexShrink: 0,
  },
  detailHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
  },
  detailEyebrow: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    color: "#6366f1",
    fontWeight: 800,
    marginBottom: 4,
  },
  detailTitle: {
    fontSize: 16,
    fontWeight: 700,
    color: "#0f172a",
  },
  detailTimestamp: {
    fontSize: 12,
    color: "#64748b",
    textAlign: "right",
    lineHeight: 1.5,
  },
  detailGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 10,
  },
  detailField: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    minWidth: 0,
  },
  detailFieldLabel: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    color: "#94a3b8",
    fontWeight: 700,
  },
  detailFieldValue: {
    fontSize: 13,
    color: "#334155",
    lineHeight: 1.45,
    wordBreak: "break-word",
  },
  detailFieldMono: {
    fontFamily: "monospace",
    fontSize: 12,
  },
  detailBody: {
    border: "1px solid #e2e8f0",
    borderRadius: 12,
    background: "#ffffff",
    padding: "12px 14px",
    fontSize: 14,
    lineHeight: 1.65,
    color: "#334155",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    maxHeight: 180,
    overflowY: "auto",
  },

  pagination: {
    display:        "flex",
    alignItems:     "center",
    justifyContent: "space-between",
    padding:        "10px 16px",
    borderTop:      "1px solid #e2e8f0",
    flexShrink:     0,
  },
  pageBtn: {
    fontSize:     13,
    padding:      "5px 12px",
    border:       "1px solid #e2e8f0",
    borderRadius: 6,
    background:   "#f8fafc",
    color:        "#374151",
    cursor:       "pointer",
    fontFamily:   "inherit",
  },
  pageInfo: { fontSize: 13, color: "#94a3b8" },
};

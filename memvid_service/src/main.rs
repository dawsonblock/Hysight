/// memvid-sidecar — Axum HTTP server implementing the HCA memory contract.
///
/// Exposes endpoints matching /app/contract/schema.json:
///   POST /memory/ingest    → store a CandidateMemory (Tantivy BM25 + WAL)
///   POST /memory/retrieve  → BM25-scored retrieval via real Tantivy engine
///   POST /memory/maintain  → TTL expiry + stats
///   GET  /memory/list      → list stored memories
///   DELETE /memory/:id     → hard-delete a memory (persisted)
///
/// Env vars:
///   MEMORY_SERVICE_PORT   (default 3031)
///   MEMORY_DATA_DIR       (default ./data)
///   RUST_LOG              (default info)

use axum::{
    extract::State,
    http::StatusCode,
    response::Json,
    routing::post,
    Router,
};
use chrono::{DateTime, Duration, Utc};
use memvid_core::{AclEnforcementMode, Memvid, PutOptions, SearchRequest, TimelineQuery};
use serde::{Deserialize, Serialize};
use std::{
    collections::{HashMap, HashSet},
    fs::{self, OpenOptions},
    io::{BufRead, BufReader, Write},
    num::NonZeroU64,
    path::PathBuf,
    sync::{Arc, Mutex},
};
use tokio::net::TcpListener;
use tower_http::cors::CorsLayer;
use uuid::Uuid;

// ── Contract types (mirrors /app/contract/schema.json) ───────────────────────

#[derive(Debug, Clone, Deserialize, Serialize)]
struct Provenance {
    source_type: String,
    source_id: String,
    source_label: Option<String>,
    trust_weight: f64,
}

impl Default for Provenance {
    fn default() -> Self {
        Self {
            source_type: "system".into(),
            source_id: Uuid::new_v4().to_string(),
            source_label: None,
            trust_weight: 0.5,
        }
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
struct CandidateMemory {
    candidate_id: Option<String>,
    raw_text: String,
    memory_type: String,
    #[serde(default)]
    entity: String,
    #[serde(default)]
    slot: String,
    #[serde(default)]
    value: String,
    #[serde(default = "half")]
    confidence: f64,
    #[serde(default = "half")]
    salience: f64,
    #[serde(default = "private_scope")]
    scope: String,
    run_id: Option<String>,
    workflow_key: Option<String>,
    #[serde(default)]
    source: Provenance,
    #[serde(default)]
    tags: Vec<String>,
    #[serde(default)]
    metadata: HashMap<String, serde_json::Value>,
}

fn half() -> f64 { 0.5 }
fn private_scope() -> String { "private".into() }

#[derive(Debug, Clone, Deserialize, Serialize)]
struct RetrievalQuery {
    query_text: String,
    #[serde(default = "default_top_k")]
    top_k: usize,
    memory_layer: Option<String>,
    scope: Option<String>,
    run_id: Option<String>,
    #[serde(default)]
    include_expired: bool,
    #[serde(default = "general_intent")]
    intent: String,
}

fn default_top_k() -> usize { 10 }
fn general_intent() -> String { "general".into() }

#[derive(Debug, Clone, Serialize, Deserialize)]
struct RetrievalHit {
    memory_id: Option<String>,
    belief_id: Option<String>,
    memory_layer: String,
    memory_type: Option<String>,
    entity: Option<String>,
    slot: Option<String>,
    value: Option<String>,
    text: String,
    score: f64,
    confidence: f64,
    stored_at: DateTime<Utc>,
    expired: bool,
    metadata: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize)]
struct IngestResponse {
    memory_id: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
struct RetrieveResponse {
    hits: Vec<RetrievalHit>,
}

#[derive(Debug, Clone, Serialize)]
struct MaintenanceReport {
    durable_memory_count: usize,
    expired_count: usize,
    expired_ids: Vec<String>,
    compaction_supported: bool,
    compactor_status: String,
}

// ── Internal record (in-memory metadata index) ────────────────────────────────

#[derive(Debug, Clone)]
struct MemoryRecord {
    memory_id: String,
    raw_text: String,
    memory_type: String,
    entity: String,
    slot: String,
    value: String,
    confidence: f64,
    scope: String,
    run_id: Option<String>,
    metadata: HashMap<String, serde_json::Value>,
    stored_at: DateTime<Utc>,
    expired: bool,
}

// ── Persistent store backed by memvid-core (Tantivy BM25 + WAL) ──────────────

struct PersistentMemoryStore {
    /// Memvid kernel: WAL persistence + Tantivy BM25 index.
    memvid: Memvid,
    /// In-memory metadata index rebuilt from Memvid frames on startup.
    records: HashMap<String, MemoryRecord>,
    /// Set of permanently-deleted memory IDs (survives restarts).
    deleted_ids: HashSet<String>,
    /// Path to the append-only deleted_ids file.
    deleted_ids_path: PathBuf,
}

impl PersistentMemoryStore {
    fn new(data_dir: PathBuf) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        fs::create_dir_all(&data_dir)?;

        let mv2_path = data_dir.join("memory.mv2");
        let deleted_ids_path = data_dir.join("deleted_ids.txt");

        // Load persisted deleted IDs.
        let deleted_ids: HashSet<String> = if deleted_ids_path.exists() {
            let f = fs::File::open(&deleted_ids_path)?;
            BufReader::new(f)
                .lines()
                .filter_map(|l| l.ok())
                .filter(|l| !l.trim().is_empty())
                .collect()
        } else {
            HashSet::new()
        };

        // Open or create the .mv2 file (WAL + Tantivy index live inside it).
        let mut memvid = if mv2_path.exists() {
            tracing::info!("Opening existing memory store: {}", mv2_path.display());
            Memvid::open(&mv2_path)?
        } else {
            tracing::info!("Creating new memory store: {}", mv2_path.display());
            Memvid::create(&mv2_path)?
        };

        // Rebuild in-memory metadata map by scanning all stored frames.
        let mut records: HashMap<String, MemoryRecord> = HashMap::new();
        let tq = TimelineQuery {
            limit: NonZeroU64::new(1_000_000),
            since: None,
            until: None,
            reverse: false,
        };

        let entries = memvid.timeline(tq).unwrap_or_default();
        tracing::info!("Scanning {} frames from memory store…", entries.len());

        for entry in entries {
            // Collect metadata fields from the TOC (cheap, no disk seek).
            let frame = match memvid.frame_by_id(entry.frame_id) {
                Ok(f) => f,
                Err(e) => {
                    tracing::warn!("Skipping frame {}: {e}", entry.frame_id);
                    continue;
                }
            };

            let meta = &frame.extra_metadata;

            // Only process our HCA-written frames.
            let memory_id = match meta.get("hca_memory_id") {
                Some(id) => id.clone(),
                None => continue,
            };

            // Skip permanently deleted frames.
            if deleted_ids.contains(&memory_id) {
                continue;
            }

            // Skip expiry-marker frames.
            if meta.get("hca_expired").map(|s| s == "true").unwrap_or(false) {
                continue;
            }

            let memory_type = meta.get("hca_memory_type").cloned().unwrap_or_default();
            let entity      = meta.get("hca_entity").cloned().unwrap_or_default();
            let slot        = meta.get("hca_slot").cloned().unwrap_or_default();
            let value       = meta.get("hca_value").cloned().unwrap_or_default();
            let confidence  = meta.get("hca_confidence")
                .and_then(|s| s.parse::<f64>().ok())
                .unwrap_or(0.5);
            let scope       = meta.get("hca_scope").cloned().unwrap_or_else(|| "private".into());
            let run_id      = meta.get("hca_run_id").cloned();
            let stored_at   = meta.get("hca_stored_at")
                .and_then(|s| chrono::DateTime::parse_from_rfc3339(s).ok())
                .map(|dt| dt.with_timezone(&Utc))
                .unwrap_or_else(Utc::now);

            let frame_id = entry.frame_id;
            // Release immutable borrow before the &mut call below.
            drop(frame);

            // Read the actual stored text payload (disk seek, but only at startup).
            let raw_text = memvid
                .frame_text_by_id(frame_id)
                .unwrap_or_else(|_| entry.preview.clone());

            records.insert(
                memory_id.clone(),
                MemoryRecord {
                    memory_id,
                    raw_text,
                    memory_type,
                    entity,
                    slot,
                    value,
                    confidence,
                    scope,
                    run_id,
                    metadata: HashMap::new(),
                    stored_at,
                    expired: false,
                },
            );
        }

        tracing::info!("Loaded {} memories from persistent store.", records.len());

        Ok(Self {
            memvid,
            records,
            deleted_ids,
            deleted_ids_path,
        })
    }

    // ── Ingest ────────────────────────────────────────────────────────────────

    fn ingest(&mut self, candidate: CandidateMemory) -> Result<String, memvid_core::MemvidError> {
        let memory_id = Uuid::new_v4().to_string();
        let now = Utc::now();

        // Build extra_metadata that will be persisted inside the .mv2 frame.
        let mut extra_metadata = std::collections::BTreeMap::new();
        extra_metadata.insert("hca_memory_id".into(),    memory_id.clone());
        extra_metadata.insert("hca_memory_type".into(),  candidate.memory_type.clone());
        extra_metadata.insert("hca_entity".into(),       candidate.entity.clone());
        extra_metadata.insert("hca_slot".into(),         candidate.slot.clone());
        extra_metadata.insert("hca_value".into(),        candidate.value.clone());
        extra_metadata.insert("hca_confidence".into(),   candidate.confidence.to_string());
        extra_metadata.insert("hca_scope".into(),        candidate.scope.clone());
        extra_metadata.insert("hca_stored_at".into(),    now.to_rfc3339());
        extra_metadata.insert("hca_expired".into(),      "false".into());
        if let Some(ref rid) = candidate.run_id {
            extra_metadata.insert("hca_run_id".into(), rid.clone());
        }
        if let Some(ref wk) = candidate.workflow_key {
            extra_metadata.insert("hca_workflow_key".into(), wk.clone());
        }
        if !candidate.tags.is_empty() {
            extra_metadata.insert("hca_tags".into(), candidate.tags.join(","));
        }

        // Write to Memvid — this appends to the WAL and updates the Tantivy index.
        self.memvid.put_bytes_with_options(
            candidate.raw_text.as_bytes(),
            PutOptions {
                uri:            Some(format!("mv2://hca-memory/{memory_id}")),
                title:          Some(candidate.raw_text.chars().take(80).collect()),
                search_text:    Some(candidate.raw_text.clone()),
                extra_metadata,
                timestamp:      Some(now.timestamp()),
                tags:           candidate.tags.clone(),
                // Disable heavy NLP processing not needed for plain text memories.
                auto_tag:          false,
                extract_dates:     false,
                extract_triplets:  false,
                instant_index:     true,  // Searchable immediately after commit.
                ..PutOptions::default()
            },
        )?;
        // Flush WAL to disk — memory now survives a crash or restart.
        self.memvid.commit()?;

        // Mirror into the in-memory index for fast list / delete access.
        self.records.insert(
            memory_id.clone(),
            MemoryRecord {
                memory_id:   memory_id.clone(),
                raw_text:    candidate.raw_text,
                memory_type: candidate.memory_type,
                entity:      candidate.entity,
                slot:        candidate.slot,
                value:       candidate.value,
                confidence:  candidate.confidence,
                scope:       candidate.scope,
                run_id:      candidate.run_id,
                metadata:    candidate.metadata,
                stored_at:   now,
                expired:     false,
            },
        );

        Ok(memory_id)
    }

    // ── Retrieve (real Tantivy BM25) ──────────────────────────────────────────

    fn retrieve(&mut self, query: &RetrievalQuery) -> Vec<RetrievalHit> {
        // Expand top_k to gather extra candidates for post-filter.
        let fetch_k = (query.top_k * 4).max(50);

        let request = SearchRequest {
            query:               query.query_text.clone(),
            top_k:               fetch_k,
            snippet_chars:       300,
            uri:                 None,
            scope:               None,
            cursor:              None,
            as_of_frame:         None,
            as_of_ts:            None,
            no_sketch:           false,
            acl_context:         None,
            acl_enforcement_mode: AclEnforcementMode::default(),
        };

        let response = match self.memvid.search(request) {
            Ok(r)  => r,
            Err(e) => {
                tracing::error!("Tantivy BM25 search error: {e}");
                return vec![];
            }
        };

        tracing::debug!(
            "Tantivy search '{}' → {} raw hits in {}ms",
            query.query_text,
            response.total_hits,
            response.elapsed_ms
        );

        let mut hits = Vec::new();

        for hit in response.hits {
            // Extract our HCA memory ID from the frame's extra_metadata.
            let memory_id = hit
                .metadata
                .as_ref()
                .and_then(|m| m.extra_metadata.get("hca_memory_id"))
                .cloned();

            let Some(mid) = memory_id else { continue };
            let Some(record) = self.records.get(&mid) else { continue };

            // Apply caller-supplied filters.
            if record.expired && !query.include_expired { continue; }
            if let Some(ref ml) = query.memory_layer {
                if ml != "trace" { continue; }
            }
            if let Some(ref s) = query.scope {
                if s != &record.scope { continue; }
            }
            if let Some(ref rid) = query.run_id {
                if record.run_id.as_deref() != Some(rid.as_str()) { continue; }
            }

            hits.push(RetrievalHit {
                memory_id:    Some(mid),
                belief_id:    None,
                memory_layer: "trace".into(),
                memory_type:  Some(record.memory_type.clone()),
                entity:       Some(record.entity.clone()),
                slot:         Some(record.slot.clone()),
                value:        Some(record.value.clone()),
                text:         record.raw_text.clone(),
                // Tantivy BM25 score (f32 → f64).
                score:        hit.score.unwrap_or(0.05) as f64,
                confidence:   record.confidence,
                stored_at:    record.stored_at,
                expired:      record.expired,
                metadata:     record.metadata.clone(),
            });
        }

        hits.truncate(query.top_k);
        hits
    }

    // ── Maintain (TTL expiry) ─────────────────────────────────────────────────

    fn maintain(&mut self) -> MaintenanceReport {
        let now = Utc::now();
        let ttl = Duration::days(7);
        let mut expired_ids  = Vec::new();
        let mut to_expire    = Vec::new();
        let mut durable      = 0_usize;

        for (id, rec) in &self.records {
            if rec.expired {
                expired_ids.push(id.clone());
            } else if now - rec.stored_at > ttl {
                to_expire.push(id.clone());
            } else if matches!(
                rec.memory_type.as_str(),
                "fact" | "episode" | "preference" | "goalstate" | "procedure"
            ) {
                durable += 1;
            }
        }

        for id in &to_expire {
            if let Some(rec) = self.records.get_mut(id) {
                rec.expired = true;
                expired_ids.push(id.clone());
            }
        }

        MaintenanceReport {
            durable_memory_count: durable,
            expired_count:        expired_ids.len(),
            expired_ids,
            compaction_supported: false,
            compactor_status:     "ok".into(),
        }
    }

    // ── Delete (persisted to deleted_ids.txt) ─────────────────────────────────

    fn delete(&mut self, memory_id: &str) -> bool {
        if self.records.remove(memory_id).is_some() {
            self.deleted_ids.insert(memory_id.to_string());
            // Append to the on-disk deleted-IDs file so deletion survives restart.
            if let Ok(mut f) = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&self.deleted_ids_path)
            {
                let _ = writeln!(f, "{memory_id}");
            }
            true
        } else {
            false
        }
    }
}

// ── App state ─────────────────────────────────────────────────────────────────

type AppState = Arc<Mutex<PersistentMemoryStore>>;

// ── HTTP handlers ─────────────────────────────────────────────────────────────

async fn ingest_handler(
    State(store): State<AppState>,
    Json(candidate): Json<CandidateMemory>,
) -> Result<Json<IngestResponse>, StatusCode> {
    let memory_id = store
        .lock()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ingest(candidate)
        .map_err(|e| {
            tracing::error!("Ingest error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(IngestResponse { memory_id: Some(memory_id) }))
}

async fn retrieve_handler(
    State(store): State<AppState>,
    Json(query): Json<RetrievalQuery>,
) -> Result<Json<RetrieveResponse>, StatusCode> {
    let hits = store
        .lock()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .retrieve(&query);
    Ok(Json(RetrieveResponse { hits }))
}

async fn maintain_handler(
    State(store): State<AppState>,
) -> Result<Json<MaintenanceReport>, StatusCode> {
    let report = store
        .lock()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .maintain();
    Ok(Json(report))
}

// ── List handler ──────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
struct ListQuery {
    memory_type:     Option<String>,
    scope:           Option<String>,
    include_expired: Option<bool>,
    limit:           Option<usize>,
    offset:          Option<usize>,
}

#[derive(Debug, Serialize)]
struct ListResponse {
    records: Vec<MemoryListItem>,
    total:   usize,
}

#[derive(Debug, Clone, Serialize)]
struct MemoryListItem {
    memory_id:   String,
    memory_type: String,
    text:        String,
    scope:       String,
    confidence:  f64,
    stored_at:   DateTime<Utc>,
    expired:     bool,
    run_id:      Option<String>,
}

async fn list_handler(
    State(store): State<AppState>,
    axum::extract::Query(q): axum::extract::Query<ListQuery>,
) -> Result<Json<ListResponse>, StatusCode> {
    let guard = store
        .lock()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let include_expired = q.include_expired.unwrap_or(false);
    let limit  = q.limit.unwrap_or(50);
    let offset = q.offset.unwrap_or(0);

    let mut filtered: Vec<&MemoryRecord> = guard
        .records
        .values()
        .filter(|r| {
            (include_expired || !r.expired)
                && q.memory_type.as_deref().map_or(true, |mt| mt == r.memory_type)
                && q.scope.as_deref().map_or(true, |s| s == r.scope)
        })
        .collect();

    filtered.sort_by(|a, b| b.stored_at.cmp(&a.stored_at));
    let total = filtered.len();

    let records = filtered
        .into_iter()
        .skip(offset)
        .take(limit)
        .map(|r| MemoryListItem {
            memory_id:   r.memory_id.clone(),
            memory_type: r.memory_type.clone(),
            text:        r.raw_text.clone(),
            scope:       r.scope.clone(),
            confidence:  r.confidence,
            stored_at:   r.stored_at,
            expired:     r.expired,
            run_id:      r.run_id.clone(),
        })
        .collect();

    Ok(Json(ListResponse { records, total }))
}

// ── Delete handler ────────────────────────────────────────────────────────────

async fn delete_handler(
    State(store): State<AppState>,
    axum::extract::Path(memory_id): axum::extract::Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    let deleted = store
        .lock()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .delete(&memory_id);

    Ok(Json(serde_json::json!({ "deleted": deleted, "memory_id": memory_id })))
}

// ── Entry point ───────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into()),
        )
        .init();

    let port     = std::env::var("MEMORY_SERVICE_PORT").unwrap_or_else(|_| "3031".into());
    let data_dir = std::env::var("MEMORY_DATA_DIR")
        .unwrap_or_else(|_| "./data".into());

    tracing::info!("memvid-sidecar v2 starting (Tantivy BM25 + WAL persistence)");
    tracing::info!("Data directory: {data_dir}");

    let store_result = PersistentMemoryStore::new(PathBuf::from(data_dir));
    let store = match store_result {
        Ok(s)  => s,
        Err(e) => {
            tracing::error!("Failed to open memory store: {e}");
            std::process::exit(1);
        }
    };

    let state: AppState = Arc::new(Mutex::new(store));

    let app = Router::new()
        .route("/memory/ingest",   post(ingest_handler))
        .route("/memory/retrieve", post(retrieve_handler))
        .route("/memory/maintain", post(maintain_handler))
        .route("/memory/list",     axum::routing::get(list_handler))
        .route("/memory/:id",      axum::routing::delete(delete_handler))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let addr = format!("0.0.0.0:{port}");
    tracing::info!("memvid-sidecar listening on {addr}");
    tracing::info!("Backend: Tantivy BM25 (memvid-core lex feature) + WAL persistence");

    let listener = TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

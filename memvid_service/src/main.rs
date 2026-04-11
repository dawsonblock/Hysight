/// memvid-sidecar v3 — Axum HTTP server implementing the HCA memory contract.
///
/// New in v3:
///   • Session isolation — per-user persistent memory stores (data/user_<id>/)
///   • Semantic HNSW search — 384-dim embeddings (Python-computed) indexed via
///     the `hnsw` crate; survives restarts via JSON embedding stored in frames.
///
/// Routes:
///   POST /memory/ingest      → store CandidateMemory (BM25 + optional HNSW)
///   POST /memory/retrieve    → BM25 or semantic/hybrid retrieval
///   POST /memory/maintain    → TTL expiry
///   GET  /memory/list        → paginated list
///   DELETE /memory/:id       → hard-delete (persisted)
///   GET  /health             → liveness
use axum::{extract::State, http::StatusCode, response::Json, routing::post, Router};
use chrono::{DateTime, Duration, Utc};
use hnsw::{Hnsw, Params, Searcher};
use memvid_core::{AclEnforcementMode, Memvid, PutOptions, SearchRequest, TimelineQuery};
use rand_pcg::Pcg64;
use serde::{Deserialize, Serialize};
use space::Metric;
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

// ── HNSW L2 metric ────────────────────────────────────────────────────────────

const HNSW_DIST_SCALE: f32 = 100_000.0;

struct L2Metric;
impl Metric<Vec<f32>> for L2Metric {
    type Unit = u32;
    fn distance(&self, a: &Vec<f32>, b: &Vec<f32>) -> u32 {
        let d: f32 = a
            .iter()
            .zip(b.iter())
            .map(|(x, y)| (x - y).powi(2))
            .sum::<f32>()
            .sqrt();
        (d * HNSW_DIST_SCALE).min(u32::MAX as f32) as u32
    }
}

// ── In-process HNSW index ─────────────────────────────────────────────────────

struct SidecarVecIndex {
    graph: Hnsw<L2Metric, Vec<f32>, Pcg64, 16, 32>,
    /// memory_id at each insertion position (0-based index).
    ids: Vec<String>,
}

impl SidecarVecIndex {
    fn new() -> Self {
        Self {
            graph: Hnsw::new_params(L2Metric, Params::new().ef_construction(100)),
            ids: Vec::new(),
        }
    }

    fn insert(&mut self, memory_id: String, embedding: Vec<f32>) {
        let mut s = Searcher::default();
        self.graph.insert(embedding, &mut s);
        self.ids.push(memory_id);
    }

    fn search(&self, query: &[f32], limit: usize) -> Vec<(String, f32)> {
        if self.ids.is_empty() {
            return vec![];
        }
        let ef = 50_usize.max(limit);
        let mut dest = vec![
            space::Neighbor::<u32> {
                index: !0,
                distance: 0
            };
            ef
        ];
        let mut s: Searcher<u32> = Searcher::default();
        let q: Vec<f32> = query.to_vec();
        let found = self.graph.nearest(&q, ef, &mut s, &mut dest);
        found
            .iter()
            .take(limit)
            .filter_map(|n| {
                self.ids.get(n.index).map(|id| {
                    let dist = n.distance as f32 / HNSW_DIST_SCALE;
                    let score = 1.0_f32 / (1.0 + dist);
                    (id.clone(), score)
                })
            })
            .collect()
    }

    fn len(&self) -> usize {
        self.ids.len()
    }
}

// ── Contract types ────────────────────────────────────────────────────────────

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
    /// Session / user-scoped isolation key.
    #[serde(default = "default_user")]
    user_id: String,
    /// Pre-computed embedding vector (384-dim bge-small-en-v1.5).
    #[serde(default)]
    embedding: Option<Vec<f32>>,
}

fn half() -> f64 {
    0.5
}
fn private_scope() -> String {
    "private".into()
}
fn default_user() -> String {
    "default".into()
}

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
    /// Session isolation key.
    #[serde(default = "default_user")]
    user_id: String,
    /// Pre-computed query embedding for semantic/hybrid search.
    #[serde(default)]
    embedding: Option<Vec<f32>>,
    /// "bm25" | "semantic" | "hybrid" (default: "bm25")
    #[serde(default = "bm25_mode")]
    mode: String,
}

fn default_top_k() -> usize {
    10
}
fn general_intent() -> String {
    "general".into()
}
fn bm25_mode() -> String {
    "bm25".into()
}

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

#[derive(Debug, Clone, Deserialize, Default)]
struct MaintainRequest {
    #[serde(default = "default_user")]
    user_id: String,
}

// ── In-memory record ──────────────────────────────────────────────────────────

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

// ── Per-user persistent store ─────────────────────────────────────────────────

struct PersistentMemoryStore {
    memvid: Memvid,
    records: HashMap<String, MemoryRecord>,
    vec_index: SidecarVecIndex,
    deleted_ids: HashSet<String>,
    deleted_ids_path: PathBuf,
}

impl PersistentMemoryStore {
    fn new(data_dir: PathBuf) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        fs::create_dir_all(&data_dir)?;

        let mv2_path = data_dir.join("memory.mv2");
        let deleted_ids_path = data_dir.join("deleted_ids.txt");

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

        let mut memvid = if mv2_path.exists() {
            tracing::info!("Opening store: {}", mv2_path.display());
            Memvid::open(&mv2_path)?
        } else {
            tracing::info!("Creating store: {}", mv2_path.display());
            Memvid::create(&mv2_path)?
        };

        // Rebuild in-memory metadata + HNSW from stored frames.
        let mut records: HashMap<String, MemoryRecord> = HashMap::new();
        let mut vec_index = SidecarVecIndex::new();

        let tq = TimelineQuery {
            limit: NonZeroU64::new(1_000_000),
            since: None,
            until: None,
            reverse: false,
        };

        let entries = memvid.timeline(tq).unwrap_or_default();
        tracing::info!("Scanning {} frames…", entries.len());

        for entry in entries {
            let frame = match memvid.frame_by_id(entry.frame_id) {
                Ok(f) => f,
                Err(_) => continue,
            };
            let meta = &frame.extra_metadata;

            let memory_id = match meta.get("hca_memory_id") {
                Some(id) => id.clone(),
                None => continue,
            };
            if deleted_ids.contains(&memory_id) {
                continue;
            }
            if meta
                .get("hca_expired")
                .map(|s| s == "true")
                .unwrap_or(false)
            {
                continue;
            }

            let stored_at = meta
                .get("hca_stored_at")
                .and_then(|s| chrono::DateTime::parse_from_rfc3339(s).ok())
                .map(|dt| dt.with_timezone(&Utc))
                .unwrap_or_else(Utc::now);

            let frame_id = entry.frame_id;
            drop(frame); // release &self borrow before &mut call

            let raw_text = memvid
                .frame_text_by_id(frame_id)
                .unwrap_or_else(|_| entry.preview.clone());

            // Rebuild HNSW if embedding was stored.
            let frame2 = memvid.frame_by_id(frame_id).ok();
            if let Some(f2) = frame2 {
                let meta2 = &f2.extra_metadata;
                if let Some(emb_str) = meta2.get("hca_embedding") {
                    if let Ok(emb) = serde_json::from_str::<Vec<f32>>(emb_str) {
                        vec_index.insert(memory_id.clone(), emb);
                    }
                }

                records.insert(
                    memory_id.clone(),
                    MemoryRecord {
                        memory_id,
                        raw_text,
                        memory_type: meta2.get("hca_memory_type").cloned().unwrap_or_default(),
                        entity: meta2.get("hca_entity").cloned().unwrap_or_default(),
                        slot: meta2.get("hca_slot").cloned().unwrap_or_default(),
                        value: meta2.get("hca_value").cloned().unwrap_or_default(),
                        confidence: meta2
                            .get("hca_confidence")
                            .and_then(|s| s.parse().ok())
                            .unwrap_or(0.5),
                        scope: meta2
                            .get("hca_scope")
                            .cloned()
                            .unwrap_or_else(|| "private".into()),
                        run_id: meta2.get("hca_run_id").cloned(),
                        metadata: HashMap::new(),
                        stored_at,
                        expired: false,
                    },
                );
            }
        }

        tracing::info!(
            "Loaded {} memories ({} with embeddings).",
            records.len(),
            vec_index.len()
        );

        Ok(Self {
            memvid,
            records,
            vec_index,
            deleted_ids,
            deleted_ids_path,
        })
    }

    // ── Ingest ─────────────────────────────────────────────────────────────

    fn ingest(&mut self, candidate: CandidateMemory) -> Result<String, memvid_core::MemvidError> {
        let memory_id = Uuid::new_v4().to_string();
        let now = Utc::now();

        let mut extra_metadata = std::collections::BTreeMap::new();
        extra_metadata.insert("hca_memory_id".into(), memory_id.clone());
        extra_metadata.insert("hca_memory_type".into(), candidate.memory_type.clone());
        extra_metadata.insert("hca_entity".into(), candidate.entity.clone());
        extra_metadata.insert("hca_slot".into(), candidate.slot.clone());
        extra_metadata.insert("hca_value".into(), candidate.value.clone());
        extra_metadata.insert("hca_confidence".into(), candidate.confidence.to_string());
        extra_metadata.insert("hca_scope".into(), candidate.scope.clone());
        extra_metadata.insert("hca_stored_at".into(), now.to_rfc3339());
        extra_metadata.insert("hca_expired".into(), "false".into());
        if let Some(ref rid) = candidate.run_id {
            extra_metadata.insert("hca_run_id".into(), rid.clone());
        }
        if !candidate.tags.is_empty() {
            extra_metadata.insert("hca_tags".into(), candidate.tags.join(","));
        }

        // Store pre-computed embedding in frame metadata for restart recovery.
        if let Some(ref emb) = candidate.embedding {
            if let Ok(s) = serde_json::to_string(emb) {
                extra_metadata.insert("hca_embedding".into(), s);
            }
        }

        self.memvid.put_bytes_with_options(
            candidate.raw_text.as_bytes(),
            PutOptions {
                uri: Some(format!("mv2://hca-memory/{memory_id}")),
                title: Some(candidate.raw_text.chars().take(80).collect()),
                search_text: Some(candidate.raw_text.clone()),
                extra_metadata,
                timestamp: Some(now.timestamp()),
                tags: candidate.tags.clone(),
                auto_tag: false,
                extract_dates: false,
                extract_triplets: false,
                instant_index: true,
                ..PutOptions::default()
            },
        )?;
        self.memvid.commit()?;

        // Insert into HNSW if embedding was provided.
        if let Some(emb) = candidate.embedding.clone() {
            self.vec_index.insert(memory_id.clone(), emb);
        }

        self.records.insert(
            memory_id.clone(),
            MemoryRecord {
                memory_id: memory_id.clone(),
                raw_text: candidate.raw_text,
                memory_type: candidate.memory_type,
                entity: candidate.entity,
                slot: candidate.slot,
                value: candidate.value,
                confidence: candidate.confidence,
                scope: candidate.scope,
                run_id: candidate.run_id,
                metadata: candidate.metadata,
                stored_at: now,
                expired: false,
            },
        );

        Ok(memory_id)
    }

    // ── Retrieve ───────────────────────────────────────────────────────────

    fn retrieve(&mut self, query: &RetrievalQuery) -> Vec<RetrievalHit> {
        match query.mode.as_str() {
            "semantic" => self.retrieve_semantic(query),
            "hybrid" => self.retrieve_hybrid(query),
            _ => self.retrieve_bm25(query),
        }
    }

    fn retrieve_bm25(&mut self, query: &RetrievalQuery) -> Vec<RetrievalHit> {
        let fetch_k = (query.top_k * 4).max(50);
        let request = SearchRequest {
            query: query.query_text.clone(),
            top_k: fetch_k,
            snippet_chars: 300,
            uri: None,
            scope: None,
            cursor: None,
            as_of_frame: None,
            as_of_ts: None,
            no_sketch: false,
            acl_context: None,
            acl_enforcement_mode: AclEnforcementMode::default(),
        };
        let response = match self.memvid.search(request) {
            Ok(r) => r,
            Err(e) => {
                tracing::error!("Tantivy search error: {e}");
                return vec![];
            }
        };

        let mut hits = Vec::new();
        for hit in response.hits {
            let mid = hit
                .metadata
                .as_ref()
                .and_then(|m| m.extra_metadata.get("hca_memory_id"))
                .cloned();
            let Some(mid) = mid else { continue };
            let Some(record) = self.records.get(&mid) else {
                continue;
            };
            if !self.passes_filter(record, query) {
                continue;
            }

            hits.push(self.make_hit(record, hit.score.unwrap_or(0.05) as f64));
        }
        hits.truncate(query.top_k);
        hits
    }

    fn retrieve_semantic(&self, query: &RetrievalQuery) -> Vec<RetrievalHit> {
        let Some(ref emb) = query.embedding else {
            tracing::warn!(
                "semantic mode requested but no embedding in query — fallback to no results"
            );
            return vec![];
        };

        let candidates = self.vec_index.search(emb, query.top_k * 4);
        let mut hits = Vec::new();
        for (mid, score) in candidates {
            let Some(record) = self.records.get(&mid) else {
                continue;
            };
            if !self.passes_filter(record, query) {
                continue;
            }
            hits.push(self.make_hit(record, score as f64));
        }
        hits.truncate(query.top_k);
        hits
    }

    fn retrieve_hybrid(&mut self, query: &RetrievalQuery) -> Vec<RetrievalHit> {
        // Collect BM25 scores.
        let bm25_hits = self.retrieve_bm25(query);
        let mut score_map: HashMap<String, f64> = bm25_hits
            .iter()
            .filter_map(|h| h.memory_id.clone().map(|id| (id, h.score)))
            .collect();

        // Collect semantic scores and merge.
        if query.embedding.is_some() {
            let sem_hits = self.retrieve_semantic(query);
            for h in sem_hits {
                if let Some(mid) = h.memory_id.clone() {
                    let entry = score_map.entry(mid).or_insert(0.0);
                    *entry += h.score * 5.0; // weight semantic higher
                }
            }
        }

        let mut merged: Vec<(String, f64)> = score_map.into_iter().collect();
        merged.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        merged
            .into_iter()
            .take(query.top_k)
            .filter_map(|(mid, score)| self.records.get(&mid).map(|rec| self.make_hit(rec, score)))
            .collect()
    }

    fn passes_filter(&self, record: &MemoryRecord, query: &RetrievalQuery) -> bool {
        if record.expired && !query.include_expired {
            return false;
        }
        if let Some(ref ml) = query.memory_layer {
            if ml != "trace" {
                return false;
            }
        }
        if let Some(ref s) = query.scope {
            if s != &record.scope {
                return false;
            }
        }
        if let Some(ref rid) = query.run_id {
            if record.run_id.as_deref() != Some(rid.as_str()) {
                return false;
            }
        }
        true
    }

    fn make_hit(&self, record: &MemoryRecord, score: f64) -> RetrievalHit {
        RetrievalHit {
            memory_id: Some(record.memory_id.clone()),
            belief_id: None,
            memory_layer: "trace".into(),
            memory_type: Some(record.memory_type.clone()),
            entity: Some(record.entity.clone()),
            slot: Some(record.slot.clone()),
            value: Some(record.value.clone()),
            text: record.raw_text.clone(),
            score,
            confidence: record.confidence,
            stored_at: record.stored_at,
            expired: record.expired,
            metadata: record.metadata.clone(),
        }
    }

    // ── Maintain ────────────────────────────────────────────────────────────

    fn maintain(&mut self) -> MaintenanceReport {
        let now = Utc::now();
        let ttl = Duration::days(7);
        let mut expired_ids = Vec::new();
        let mut to_expire = Vec::new();
        let mut durable = 0_usize;

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
            expired_count: expired_ids.len(),
            expired_ids,
            compaction_supported: false,
            compactor_status: "ok".into(),
        }
    }

    // ── Delete ──────────────────────────────────────────────────────────────

    fn delete(&mut self, memory_id: &str) -> bool {
        if self.records.remove(memory_id).is_some() {
            self.deleted_ids.insert(memory_id.to_string());
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

// ── Shared state — user_id → user store ──────────────────────────────────────

struct SharedState {
    stores: HashMap<String, Arc<Mutex<PersistentMemoryStore>>>,
    data_dir: PathBuf,
}

type AppState = Arc<Mutex<SharedState>>;

fn get_or_create_user_store(
    shared: &mut SharedState,
    user_id: &str,
) -> Result<Arc<Mutex<PersistentMemoryStore>>, StatusCode> {
    if let Some(store) = shared.stores.get(user_id) {
        return Ok(store.clone());
    }
    let dir = shared.data_dir.join(format!("user_{user_id}"));
    match PersistentMemoryStore::new(dir) {
        Ok(store) => {
            let arc = Arc::new(Mutex::new(store));
            shared.stores.insert(user_id.to_string(), arc.clone());
            Ok(arc)
        }
        Err(e) => {
            tracing::error!("Failed to create store for user '{user_id}': {e}");
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

// ── HTTP handlers ─────────────────────────────────────────────────────────────

async fn ingest_handler(
    State(state): State<AppState>,
    Json(candidate): Json<CandidateMemory>,
) -> Result<Json<IngestResponse>, StatusCode> {
    let user_id = candidate.user_id.clone();
    let user_store = {
        let mut shared = state
            .lock()
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        get_or_create_user_store(&mut shared, &user_id)?
    };
    let memory_id = user_store
        .lock()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ingest(candidate)
        .map_err(|e| {
            tracing::error!("Ingest: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(IngestResponse {
        memory_id: Some(memory_id),
    }))
}

async fn retrieve_handler(
    State(state): State<AppState>,
    Json(query): Json<RetrievalQuery>,
) -> Result<Json<RetrieveResponse>, StatusCode> {
    let user_id = query.user_id.clone();
    let user_store = {
        let mut shared = state
            .lock()
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        get_or_create_user_store(&mut shared, &user_id)?
    };
    let hits = user_store
        .lock()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .retrieve(&query);
    Ok(Json(RetrieveResponse { hits }))
}

async fn maintain_handler(
    State(state): State<AppState>,
    body: Option<Json<MaintainRequest>>,
) -> Result<Json<MaintenanceReport>, StatusCode> {
    let user_id = body
        .map(|Json(b)| b.user_id)
        .unwrap_or_else(|| "default".into());
    let user_store = {
        let mut shared = state
            .lock()
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        get_or_create_user_store(&mut shared, &user_id)?
    };
    let report = user_store
        .lock()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .maintain();
    Ok(Json(report))
}

// ── List ──────────────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
struct ListQuery {
    memory_type: Option<String>,
    scope: Option<String>,
    include_expired: Option<bool>,
    limit: Option<usize>,
    offset: Option<usize>,
    user_id: Option<String>,
}

#[derive(Debug, Serialize)]
struct ListResponse {
    records: Vec<MemoryListItem>,
    total: usize,
}

#[derive(Debug, Clone, Serialize)]
struct MemoryListItem {
    memory_id: String,
    memory_layer: String,
    memory_type: String,
    text: String,
    scope: String,
    confidence: f64,
    stored_at: DateTime<Utc>,
    expired: bool,
    run_id: Option<String>,
}

async fn list_handler(
    State(state): State<AppState>,
    axum::extract::Query(q): axum::extract::Query<ListQuery>,
) -> Result<Json<ListResponse>, StatusCode> {
    let user_id = q.user_id.clone().unwrap_or_else(|| "default".into());
    let user_store = {
        let mut shared = state
            .lock()
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        get_or_create_user_store(&mut shared, &user_id)?
    };
    let guard = user_store
        .lock()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let include_expired = q.include_expired.unwrap_or(false);
    let limit = q.limit.unwrap_or(50);
    let offset = q.offset.unwrap_or(0);

    let mut filtered: Vec<&MemoryRecord> = guard
        .records
        .values()
        .filter(|r| {
            (include_expired || !r.expired)
                && q.memory_type
                    .as_deref()
                    .map_or(true, |mt| mt == r.memory_type)
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
            memory_id: r.memory_id.clone(),
            memory_layer: "trace".into(),
            memory_type: r.memory_type.clone(),
            text: r.raw_text.clone(),
            scope: r.scope.clone(),
            confidence: r.confidence,
            stored_at: r.stored_at,
            expired: r.expired,
            run_id: r.run_id.clone(),
        })
        .collect();

    Ok(Json(ListResponse { records, total }))
}

// ── Delete ────────────────────────────────────────────────────────────────────

async fn delete_handler(
    State(state): State<AppState>,
    axum::extract::Path(memory_id): axum::extract::Path<String>,
    axum::extract::Query(q): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    let user_id = q
        .get("user_id")
        .cloned()
        .unwrap_or_else(|| "default".into());
    let user_store = {
        let mut shared = state
            .lock()
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        get_or_create_user_store(&mut shared, &user_id)?
    };
    let deleted = user_store
        .lock()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .delete(&memory_id);

    if deleted {
        Ok(Json(
            serde_json::json!({ "deleted": true, "memory_id": memory_id }),
        ))
    } else {
        Err(StatusCode::NOT_FOUND)
    }
}

async fn health_handler(State(state): State<AppState>) -> Json<serde_json::Value> {
    let shared = state.lock().unwrap();
    let user_count = shared.stores.len();
    Json(serde_json::json!({
        "status":      "ok",
        "engine":      "tantivy-bm25+hnsw",
        "user_stores": user_count,
    }))
}

// ── Entry point ───────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into()))
        .init();

    let port = std::env::var("MEMORY_SERVICE_PORT").unwrap_or_else(|_| "3031".into());
    let data_dir = std::env::var("MEMORY_DATA_DIR").unwrap_or_else(|_| "./data".into());

    tracing::info!("memvid-sidecar v3 (Tantivy BM25 + HNSW semantic + session isolation)");

    // Pre-create the default user store on startup.
    let default_dir = PathBuf::from(&data_dir).join("user_default");
    let default_store = match PersistentMemoryStore::new(default_dir) {
        Ok(s) => s,
        Err(e) => {
            tracing::error!("Cannot create default store: {e}");
            std::process::exit(1);
        }
    };
    let mut stores: HashMap<String, Arc<Mutex<PersistentMemoryStore>>> = HashMap::new();
    stores.insert("default".to_string(), Arc::new(Mutex::new(default_store)));

    let state: AppState = Arc::new(Mutex::new(SharedState {
        stores,
        data_dir: PathBuf::from(data_dir),
    }));

    let app = Router::new()
        .route("/memory/ingest", post(ingest_handler))
        .route("/memory/retrieve", post(retrieve_handler))
        .route("/memory/maintain", post(maintain_handler))
        .route("/memory/list", axum::routing::get(list_handler))
        .route("/memory/:id", axum::routing::delete(delete_handler))
        .route("/health", axum::routing::get(health_handler))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let addr = format!("0.0.0.0:{port}");
    tracing::info!("Listening on {addr}");
    let listener = TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

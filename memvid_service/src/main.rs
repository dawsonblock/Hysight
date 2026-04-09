/// memvid-sidecar — Axum HTTP server implementing the HCA memory contract.
///
/// Exposes three endpoints matching /app/contract/schema.json:
///   POST /memory/ingest    → store a CandidateMemory
///   POST /memory/retrieve  → BM25-score retrieval
///   POST /memory/maintain  → TTL expiry + stats
///
/// Build & run:
///   cd /app/memvid_service
///   cargo run --release
///
/// Env vars:
///   MEMORY_SERVICE_PORT   (default 3031)
///   RUST_LOG              (default info)

use axum::{
    extract::State,
    http::StatusCode,
    response::Json,
    routing::post,
    Router,
};
use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
};
use tokio::net::TcpListener;
use tower_http::cors::CorsLayer;
use uuid::Uuid;

// ── Contract types (mirrors schema.json) ─────────────────────────────────────

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

fn half() -> f64 {
    0.5
}
fn private_scope() -> String {
    "private".into()
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
}

fn default_top_k() -> usize {
    10
}
fn general_intent() -> String {
    "general".into()
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

// ── Internal record ───────────────────────────────────────────────────────────

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

// ── BM25-lite + Store ─────────────────────────────────────────────────────────

#[derive(Default)]
struct MemoryStore {
    records: Vec<MemoryRecord>,
}

impl MemoryStore {
    fn bm25(query: &str, text: &str) -> f64 {
        let k1 = 1.5_f64;
        let b = 0.75_f64;
        let avg = 10.0_f64;
        let q_terms: Vec<&str> = query.split_whitespace().collect();
        let d_terms: Vec<&str> = text.split_whitespace().collect();
        if q_terms.is_empty() || d_terms.is_empty() {
            return 0.0;
        }
        let doc_len = d_terms.len() as f64;
        let mut tf_map: HashMap<String, usize> = HashMap::new();
        for t in &d_terms {
            *tf_map.entry(t.to_lowercase()).or_insert(0) += 1;
        }
        let mut score = 0.0_f64;
        for term in &q_terms {
            let tf = *tf_map.get(&term.to_lowercase()).unwrap_or(&0) as f64;
            if tf == 0.0 {
                continue;
            }
            // BM25 TF component (no corpus IDF — single-store scoring)
            let numer = tf * (k1 + 1.0);
            let denom = tf + k1 * (1.0 - b + b * doc_len / avg);
            score += numer / denom;
        }
        score.max(0.0)
    }

    fn ingest(&mut self, candidate: CandidateMemory) -> String {
        let memory_id = Uuid::new_v4().to_string();
        self.records.push(MemoryRecord {
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
            stored_at: Utc::now(),
            expired: false,
        });
        memory_id
    }

    fn retrieve(&self, query: &RetrievalQuery) -> Vec<RetrievalHit> {
        let mut scored: Vec<(f64, &MemoryRecord)> = self
            .records
            .iter()
            .filter(|r| {
                (!r.expired || query.include_expired)
                    && query
                        .memory_layer
                        .as_deref()
                        .map_or(true, |ml| ml == "trace")
                    && query
                        .scope
                        .as_deref()
                        .map_or(true, |s| s == r.scope.as_str())
                    && query
                        .run_id
                        .as_deref()
                        .map_or(true, |id| Some(id) == r.run_id.as_deref())
            })
            .filter_map(|r| {
                let s = Self::bm25(&query.query_text, &r.raw_text);
                if s > 0.0 {
                    Some((s, r))
                } else {
                    None
                }
            })
            .collect();

        scored.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        scored.truncate(query.top_k);

        scored
            .into_iter()
            .map(|(score, r)| RetrievalHit {
                memory_id: Some(r.memory_id.clone()),
                belief_id: None,
                memory_layer: "trace".into(),
                memory_type: Some(r.memory_type.clone()),
                entity: Some(r.entity.clone()),
                slot: Some(r.slot.clone()),
                value: Some(r.value.clone()),
                text: r.raw_text.clone(),
                score,
                confidence: r.confidence,
                stored_at: r.stored_at,
                expired: r.expired,
                metadata: r.metadata.clone(),
            })
            .collect()
    }

    fn maintain(&mut self) -> MaintenanceReport {
        let now = Utc::now();
        let ttl = Duration::days(7);
        let mut expired_ids = Vec::new();
        let mut durable = 0_usize;

        for rec in self.records.iter_mut() {
            if rec.expired {
                expired_ids.push(rec.memory_id.clone());
                continue;
            }
            if now - rec.stored_at > ttl {
                rec.expired = true;
                expired_ids.push(rec.memory_id.clone());
                continue;
            }
            if matches!(
                rec.memory_type.as_str(),
                "fact" | "episode" | "preference" | "goalstate" | "procedure"
            ) {
                durable += 1;
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
}

// ── App state ─────────────────────────────────────────────────────────────────

type AppState = Arc<Mutex<MemoryStore>>;

// ── HTTP handlers ─────────────────────────────────────────────────────────────

async fn ingest_handler(
    State(store): State<AppState>,
    Json(candidate): Json<CandidateMemory>,
) -> Result<Json<IngestResponse>, StatusCode> {
    let memory_id = store
        .lock()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ingest(candidate);
    Ok(Json(IngestResponse {
        memory_id: Some(memory_id),
    }))
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

// ── Entry point ───────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into()),
        )
        .init();

    let port = std::env::var("MEMORY_SERVICE_PORT").unwrap_or_else(|_| "3031".into());
    let addr = format!("0.0.0.0:{port}");

    let store: AppState = Arc::new(Mutex::new(MemoryStore::default()));

    let app = Router::new()
        .route("/memory/ingest", post(ingest_handler))
        .route("/memory/retrieve", post(retrieve_handler))
        .route("/memory/maintain", post(maintain_handler))
        .layer(CorsLayer::permissive())
        .with_state(store);

    tracing::info!("memvid-sidecar listening on {addr}");
    tracing::info!("Endpoints: POST /memory/ingest | /memory/retrieve | /memory/maintain");
    tracing::info!(
        "To use from Python: MEMORY_BACKEND=rust MEMORY_SERVICE_URL=http://localhost:{port}"
    );

    let listener = TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

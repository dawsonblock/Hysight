# Multi-stage Dockerfile for the memvid Rust HTTP sidecar.
# Build context: repo root  (needs both memvid/ and memvid_service/).

# --- build stage ---
# rust:slim-bookworm ships rustup; rust-toolchain.toml pins the exact channel.
FROM rust:slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy toolchain pin so rustup installs the correct version before compiling
COPY memvid/rust-toolchain.toml memvid/rust-toolchain.toml

# Copy dependency manifests first for layer-cache efficiency
COPY memvid/Cargo.toml              memvid/Cargo.toml
COPY memvid/Cargo.lock              memvid/Cargo.lock
COPY memvid_service/Cargo.toml      memvid_service/Cargo.toml
COPY memvid_service/Cargo.lock      memvid_service/Cargo.lock

# Warm the dependency cache with stub sources
RUN mkdir -p memvid/src memvid_service/src \
 && echo 'pub fn _stub() {}' > memvid/src/lib.rs \
 && echo 'fn main() {}' > memvid_service/src/main.rs \
 && cargo build --locked --release --manifest-path memvid_service/Cargo.toml \
 && rm -rf memvid/src memvid_service/src

# Build the real binary
COPY memvid/src         memvid/src
COPY memvid_service/src memvid_service/src
RUN cargo build --locked --release --manifest-path memvid_service/Cargo.toml

# --- runtime stage ---
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3 \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/target/release/memvid-sidecar /app/memvid-sidecar

# Writable data directory; bind-mount or volume in compose
RUN mkdir -p /app/data

# Non-root runtime user; only /app/data needs write access
RUN addgroup --system hysight \
 && adduser --system --ingroup hysight --no-create-home hysight \
 && chown -R hysight:hysight /app/data
USER hysight

ENV RUST_LOG=info
ENV MEMORY_SERVICE_PORT=3031

EXPOSE 3031

CMD ["/app/memvid-sidecar"]

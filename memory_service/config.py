"""Configuration helpers for the memory backend."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .types import SidecarHealthResponse


REPO_ROOT = Path(__file__).resolve().parent.parent
_VALID_MEMORY_BACKENDS = {"python", "rust"}
_SIDECAR_URL_EXAMPLE = "Example: MEMORY_SERVICE_URL=http://localhost:3031"


class MemoryConfigurationError(RuntimeError):
    """Raised when memory backend configuration is invalid."""


@dataclass(frozen=True)
class MemorySettings:
    backend: str
    storage_dir: Path
    service_url: str | None = None

    @property
    def uses_sidecar(self) -> bool:
        return self.backend == "rust"

    def endpoint(self, path: str) -> str:
        if not self.service_url:
            raise MemoryConfigurationError(
                "MEMORY_SERVICE_URL is required when MEMORY_BACKEND=rust. "
                f"{_SIDECAR_URL_EXAMPLE}"
            )
        return f"{self.service_url.rstrip('/')}{path}"


def default_memory_storage_dir() -> Path:
    return default_hca_storage_root() / "memory"


def default_hca_storage_root() -> Path:
    return REPO_ROOT / "storage"


def _normalize_configured_path(
    raw_path: str | None,
    *,
    env_name: str,
    default_path: Path,
) -> Path:
    if not raw_path or not raw_path.strip():
        return default_path.resolve()
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    raise MemoryConfigurationError(
        f"{env_name} must be an absolute path when set. "
        f"Example: {env_name}={default_path}"
    )


def _normalize_hca_storage_root(raw_path: str | None) -> Path:
    return _normalize_configured_path(
        raw_path,
        env_name="HCA_STORAGE_ROOT",
        default_path=default_hca_storage_root(),
    )


def _normalize_storage_dir(
    raw_path: str | None,
    *,
    hca_storage_root: Path,
) -> Path:
    return _normalize_configured_path(
        raw_path,
        env_name="MEMORY_STORAGE_DIR",
        default_path=hca_storage_root / "memory",
    )


def _validate_storage_layout(
    hca_storage_root: Path,
    storage_dir: Path,
) -> None:
    try:
        relative_storage_dir = storage_dir.relative_to(hca_storage_root)
    except ValueError as exc:
        raise MemoryConfigurationError(
            "MEMORY_STORAGE_DIR must be inside HCA_STORAGE_ROOT so memory "
            "and run storage stay under one explicit root. Example: "
            f"HCA_STORAGE_ROOT={hca_storage_root} "
            f"MEMORY_STORAGE_DIR={hca_storage_root / 'memory'}"
        ) from exc

    if not relative_storage_dir.parts:
        raise MemoryConfigurationError(
            "MEMORY_STORAGE_DIR must be a child directory of "
            "HCA_STORAGE_ROOT, not the root itself. Example: "
            f"MEMORY_STORAGE_DIR={hca_storage_root / 'memory'}"
        )


def _validate_service_url(service_url: str) -> None:
    parsed = urlparse(service_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise MemoryConfigurationError(
            "MEMORY_SERVICE_URL must be an absolute http(s) URL. "
            f"{_SIDECAR_URL_EXAMPLE}"
        )


def load_memory_settings() -> MemorySettings:
    raw_backend = (
        os.environ.get("MEMORY_BACKEND", "python").strip().lower()
        or "python"
    )
    if raw_backend not in _VALID_MEMORY_BACKENDS:
        allowed = ", ".join(sorted(_VALID_MEMORY_BACKENDS))
        raise MemoryConfigurationError(
            f"MEMORY_BACKEND must be one of: {allowed}"
        )

    hca_storage_root = _normalize_hca_storage_root(
        os.environ.get("HCA_STORAGE_ROOT")
    )
    storage_dir = _normalize_storage_dir(
        os.environ.get("MEMORY_STORAGE_DIR"),
        hca_storage_root=hca_storage_root,
    )
    service_url = os.environ.get("MEMORY_SERVICE_URL", "").strip() or None

    _validate_storage_layout(hca_storage_root, storage_dir)

    if raw_backend == "python" and service_url:
        raise MemoryConfigurationError(
            "MEMORY_SERVICE_URL must be unset unless MEMORY_BACKEND=rust. "
            f"{_SIDECAR_URL_EXAMPLE}"
        )

    if raw_backend == "rust":
        if not service_url:
            raise MemoryConfigurationError(
                "MEMORY_SERVICE_URL is required when MEMORY_BACKEND=rust. "
                f"{_SIDECAR_URL_EXAMPLE}"
            )
        _validate_service_url(service_url)

    return MemorySettings(
        backend=raw_backend,
        storage_dir=storage_dir,
        service_url=service_url,
    )


def validate_memory_backend_startup(timeout: float = 2.0) -> MemorySettings:
    settings = load_memory_settings()
    if settings.uses_sidecar:
        probe_memory_service(settings, timeout=timeout)
    return settings


def probe_memory_service(
    settings: MemorySettings,
    timeout: float = 2.0,
) -> None:
    if not settings.uses_sidecar:
        return

    health_url = settings.endpoint("/health")

    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - dependency validation
        raise MemoryConfigurationError(
            "httpx must be installed when MEMORY_BACKEND=rust"
        ) from exc

    try:
        response = httpx.get(health_url, timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MemoryConfigurationError(
            "Rust memory backend health check failed for "
            f"{health_url}. Verify the sidecar is running and reachable. "
            f"{_SIDECAR_URL_EXAMPLE} ({exc})"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise MemoryConfigurationError(
            f"Rust memory backend /health response from {health_url} "
            "was not valid JSON"
        ) from exc

    try:
        health = SidecarHealthResponse.model_validate(payload)
    except Exception as exc:
        raise MemoryConfigurationError(
            "Rust memory backend /health response did not match the "
            "contract. Expected JSON with fields: status, engine, "
            "user_stores"
        ) from exc

    if health.status != "ok":
        raise MemoryConfigurationError(
            "Rust memory backend /health did not report status=ok; "
            f"received status={health.status!r}"
        )

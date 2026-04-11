"""Configuration helpers for the memory backend."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parent.parent
_VALID_MEMORY_BACKENDS = {"python", "rust"}


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
                "MEMORY_SERVICE_URL is required when MEMORY_BACKEND=rust"
            )
        return f"{self.service_url.rstrip('/')}{path}"


def default_memory_storage_dir() -> Path:
    return REPO_ROOT / "storage" / "memory"


def _normalize_storage_dir(raw_path: str | None) -> Path:
    if not raw_path:
        return default_memory_storage_dir()
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _validate_service_url(service_url: str) -> None:
    parsed = urlparse(service_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise MemoryConfigurationError(
            "MEMORY_SERVICE_URL must be an absolute http(s) URL"
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

    storage_dir = _normalize_storage_dir(os.environ.get("MEMORY_STORAGE_DIR"))
    service_url = os.environ.get("MEMORY_SERVICE_URL", "").strip() or None

    if raw_backend == "rust":
        if not service_url:
            raise MemoryConfigurationError(
                "MEMORY_SERVICE_URL is required when MEMORY_BACKEND=rust"
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

    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - dependency validation
        raise MemoryConfigurationError(
            "httpx must be installed when MEMORY_BACKEND=rust"
        ) from exc

    try:
        response = httpx.get(settings.endpoint("/health"), timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MemoryConfigurationError(
            f"Rust memory backend health check failed: {exc}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise MemoryConfigurationError(
            "Rust memory backend /health response was not valid JSON"
        ) from exc

    if payload.get("status") != "ok":
        raise MemoryConfigurationError(
            "Rust memory backend /health did not report status=ok"
        )

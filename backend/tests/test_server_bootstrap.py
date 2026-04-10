import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.server import BackendConfigurationError, _load_settings


def test_load_settings_requires_backend_env(monkeypatch):
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)

    with pytest.raises(BackendConfigurationError, match="MONGO_URL, DB_NAME"):
        _load_settings()
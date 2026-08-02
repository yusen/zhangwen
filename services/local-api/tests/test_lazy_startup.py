from __future__ import annotations

from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient

from zhangwen.cad_agent import router as cad_router
from zhangwen.config import settings
from zhangwen.main import app


def test_core_api_startup_keeps_cad_coordinator_lazy(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    cad_router._coordinator = None
    started = perf_counter()

    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert cad_router._coordinator is None

    assert perf_counter() - started <= 5.0
    assert cad_router._coordinator is None

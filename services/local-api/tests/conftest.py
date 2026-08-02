from __future__ import annotations

import os
import sys

import pytest

from tests.fakes import FakeCredentialStore, StructuredFakeProvider
from tests.hardware_gate import hardware_gate_reason
from tests.hardware_seed_fixtures import seed_legacy_test_components
from zhangwen.clarification import router as clarification_router
from zhangwen.code_agent import router as code_router
from zhangwen.lesson_agent import router as lesson_router
from zhangwen.projects import router as projects_router
from zhangwen.proposals import router as proposals_router
from zhangwen.solutions import router as solutions_router
from zhangwen.specs import router as specs_router
from zhangwen.hardware.seeds import seed_default_components as production_seed_default_components


PROVIDER_BACKED_ROUTERS = (
    projects_router,
    proposals_router,
    specs_router,
    code_router,
    lesson_router,
    clarification_router,
    solutions_router,
)


@pytest.fixture(autouse=True)
def _require_explicit_hardware_authorization(
    request: pytest.FixtureRequest,
) -> None:
    """Never let a marked test reach hardware without both operator gates."""

    if request.node.get_closest_marker("hardware") is None:
        return
    reason = hardware_gate_reason(os.environ)
    if reason is not None:
        pytest.skip(reason)


@pytest.fixture(autouse=True)
def _fake_provider_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """Keep automated generation on the shared structured fake provider."""

    monkeypatch.setenv("ZHANGWEN_AUTH_DISABLED", "1")

    # Older behavior tests use an explicit multi-part fixture catalog. The
    # production-default contract is exercised separately by ZW-HW-002.
    if request.node.path.name != "test_hardware_catalog_media.py":
        monkeypatch.setenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE", "1")

        def seed_test_catalog(db_path) -> None:
            production_seed_default_components(db_path)
            seed_legacy_test_components(db_path)

        for module in tuple(sys.modules.values()):
            if module is None:
                continue
            if getattr(module, "seed_default_components", None) is production_seed_default_components:
                monkeypatch.setattr(module, "seed_default_components", seed_test_catalog)

    for router in PROVIDER_BACKED_ROUTERS:
        monkeypatch.setattr(
            router,
            "credential_store_factory",
            FakeCredentialStore,
        )
        monkeypatch.setattr(
            router,
            "provider_factory",
            StructuredFakeProvider,
        )

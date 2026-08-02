from __future__ import annotations

from tests.hardware_gate import (
    HARDWARE_CONFIRMATION_ENV,
    HARDWARE_CONFIRMATION_PHRASE,
    HARDWARE_ENABLE_ENV,
    hardware_gate_reason,
)


def test_hardware_gate_requires_enable_and_exact_manual_confirmation() -> None:
    assert HARDWARE_ENABLE_ENV in str(hardware_gate_reason({}))
    assert HARDWARE_CONFIRMATION_ENV in str(
        hardware_gate_reason({HARDWARE_ENABLE_ENV: "1"})
    )
    assert HARDWARE_ENABLE_ENV in str(
        hardware_gate_reason(
            {HARDWARE_CONFIRMATION_ENV: HARDWARE_CONFIRMATION_PHRASE}
        )
    )
    assert HARDWARE_CONFIRMATION_ENV in str(
        hardware_gate_reason(
            {
                HARDWARE_ENABLE_ENV: "1",
                HARDWARE_CONFIRMATION_ENV: "yes",
            }
        )
    )
    assert (
        hardware_gate_reason(
            {
                HARDWARE_ENABLE_ENV: "1",
                HARDWARE_CONFIRMATION_ENV: HARDWARE_CONFIRMATION_PHRASE,
            }
        )
        is None
    )


def test_pytest_defaults_exclude_registered_hardware_marker(pytestconfig) -> None:
    assert "not hardware" in pytestconfig.getini("addopts")
    assert any(
        marker.startswith("hardware:")
        for marker in pytestconfig.getini("markers")
    )

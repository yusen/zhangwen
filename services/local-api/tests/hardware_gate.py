"""Central double gate for tests that may access real hardware."""

from __future__ import annotations

from collections.abc import Mapping


HARDWARE_ENABLE_ENV = "ZHANGWEN_RUN_HARDWARE_TESTS"
HARDWARE_CONFIRMATION_ENV = "ZHANGWEN_HARDWARE_TEST_CONFIRMATION"
HARDWARE_CONFIRMATION_PHRASE = "I_UNDERSTAND_REAL_HARDWARE"


def hardware_gate_reason(environment: Mapping[str, str]) -> str | None:
    if environment.get(HARDWARE_ENABLE_ENV) != "1":
        return (
            f"{HARDWARE_ENABLE_ENV}=1 is required before collecting real-hardware "
            "acceptance tests."
        )
    if (
        environment.get(HARDWARE_CONFIRMATION_ENV)
        != HARDWARE_CONFIRMATION_PHRASE
    ):
        return (
            f"{HARDWARE_CONFIRMATION_ENV} must exactly match the documented "
            "manual confirmation phrase."
        )
    return None

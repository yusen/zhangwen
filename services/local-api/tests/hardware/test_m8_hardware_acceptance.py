"""Operator-only entry reserved for Creator M8 real-hardware acceptance."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.hardware


def test_m8_real_hardware_acceptance_remains_manual() -> None:
    pytest.skip(
        "M8 real K10/XIAO, USB and ESP-Claw acceptance remains an operator "
        "checklist; no automated test may initiate a device action."
    )

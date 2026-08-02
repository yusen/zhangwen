"""Deterministic mechanical CAD engine for Zhangwen."""

from zhangwen.cad_engine.engine import (
    CadBuildArtifacts,
    CadDesignRejected,
    CadGeometryRejected,
    build_cad_artifacts,
)
from zhangwen.cad_engine.geometry import CadRuntimeUnavailable, cadquery_available
from zhangwen.cad_engine.layout import resolve_layout
from zhangwen.cad_engine.models import CadBuildSpec
from zhangwen.cad_engine.profiles import (
    trusted_profile,
    trusted_profiles,
    unihiker_k10_profile,
    unihiker_ultrasonic_distance_sensor_profile,
)
from zhangwen.cad_engine.validation import validate_design

__all__ = [
    "CadBuildArtifacts",
    "CadBuildSpec",
    "CadDesignRejected",
    "CadGeometryRejected",
    "CadRuntimeUnavailable",
    "build_cad_artifacts",
    "cadquery_available",
    "resolve_layout",
    "trusted_profile",
    "trusted_profiles",
    "unihiker_k10_profile",
    "unihiker_ultrasonic_distance_sensor_profile",
    "validate_design",
]

"""HTTP boundary models for reviewed mechanical profiles and explicit links."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MechanicalProfileSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profileId: str
    revision: str
    displayName: str
    category: str
    dimensions: dict[str, float]
    mountingMode: str
    mountingStrategy: str
    preferredSurface: str
    allowedSurfaces: list[str]
    clearance: float
    evidenceLevel: str
    representation: str
    coordinateSystem: dict[str, str]
    modelKind: str
    previewGeometry: dict[str, object] | None
    mountingHoles: list[dict[str, object]]
    openings: list[dict[str, object]]
    keepouts: list[dict[str, object]]
    contentSha256: str
    confirmedHardwareIds: list[str]
    lockedHardwareIds: list[str]


class MechanicalProfileListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profiles: list[MechanicalProfileSummary]


class GenerateMechanicalProfilePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: str = Field(min_length=1, max_length=160)


class MechanicalProfilePreviewGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: MechanicalProfileSummary
    generationSource: Literal[
        "DESCRIPTION_CACHE",
        "DESCRIPTION_GENERATED",
        "ENVELOPE_FALLBACK",
    ]


class ConfirmMechanicalProfileLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profileId: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,119}$")
    revision: str = Field(min_length=1, max_length=160)


class MechanicalProfileLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hardwareId: str
    profileId: str
    revision: str
    confirmed: bool


class RemoveMechanicalProfileLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hardwareId: str
    removed: bool

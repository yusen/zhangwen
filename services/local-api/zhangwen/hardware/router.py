"""Hardware component HTTP routes."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import ValidationError

from zhangwen.cad_agent.profile_api import (
    ConfirmMechanicalProfileLinkRequest,
    GenerateMechanicalProfilePreviewRequest,
    MechanicalProfileLinkResponse,
    MechanicalProfileListResponse,
    MechanicalProfilePreviewGenerationResponse,
    MechanicalProfileSummary,
    RemoveMechanicalProfileLinkResponse,
)
from zhangwen.cad_agent.profile_repository import (
    MechanicalProfileRepository,
    MechanicalProfileSnapshot,
)

from zhangwen.config import settings
from zhangwen.hardware.board_profiles import (
    BoardProfileConflictError,
    BoardProfileListResponse,
    BoardProfileNotFoundError,
    BoardProfileRepository,
    BoardProfileResponse,
    BoardProfileValidationError,
    ResetBoardProfileRequest,
    UpdateBoardProfileRequest,
)
from zhangwen.hardware.hardware_skills import (
    HardwareSkillConflictError,
    HardwareSkillNotFoundError,
    HardwareSkillRepository,
    HardwareSkillValidationError,
    SUPPORTED_CONTROLLER_COMPONENT_IDS,
)
from zhangwen.hardware.mechanical_preview import (
    MechanicalDescriptionPreviewService,
    MechanicalPreviewSourceError,
    extract_mechanical_natural_description,
    mechanical_description_sha256,
    write_preview_geometry,
)
from zhangwen.hardware.models import (
    ComponentListResponse,
    ComponentResponse,
    ConfirmHardwareSkillDraftRequest,
    ContinueHardwareSkillDraftRequest,
    CreateComponentRequest,
    CreateHardwareSkillDraftRequest,
    HardwareComponentPackageResponse,
    HardwareCategory,
    HardwareComponentPackageDetail,
    HardwareComponentPackageFile,
    HardwareCatalogRefreshResponse,
    HardwareSkillDraftResponse,
    HardwareSkillListResponse,
    HardwareSkillResponse,
    UpdateHardwareComponentPackageFileRequest,
    UpdateHardwareSkillFileRequest,
    UpdateHardwareSkillFilesRequest,
    UpdateComponentRequest,
    ValidateCombinationRequest,
    ValidateCombinationResponse,
    ValidationCheck,
    ValidationResult,
    ValidationSeverity,
)
from zhangwen.hardware.repository import HardwareRepository
from zhangwen.hardware.rule_engine import validate_components
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.llm.deepseek import DeepSeekProvider
from zhangwen.llm.http import llm_http_exception
from zhangwen.llm.runtime import require_llm_config
from zhangwen.settings.models import ModelWorkload
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.projects.repository import ProjectRepository
from zhangwen.security.credentials import BackendCredentialStore

router = APIRouter(prefix="/api/hardware", tags=["hardware"])
credential_store_factory = BackendCredentialStore
provider_factory = DeepSeekProvider


@router.get(
    "/mechanical-profiles",
    response_model=MechanicalProfileListResponse,
)
async def list_mechanical_profiles() -> MechanicalProfileListResponse:
    skills = _hardware_skill_repo()
    repository = _mechanical_profile_repo()
    try:
        skills.migrate_legacy_rows()
        repository.seed_builtin_profiles()
        records = repository.list_with_confirmed_hardware()
    except (ValueError, ValidationError, HardwareSkillValidationError) as exc:
        raise _mechanical_profile_error(422, "MECHANICAL_PROFILE_INVALID", str(exc)) from exc
    return MechanicalProfileListResponse(
        profiles=[
            _mechanical_profile_summary(snapshot, hardware_ids, locked_ids)
            for snapshot, hardware_ids, locked_ids in records
        ]
    )


@router.post(
    "/mechanical-profiles/{profile_id}/preview",
    response_model=MechanicalProfilePreviewGenerationResponse,
)
async def generate_mechanical_profile_preview(
    profile_id: str,
    request: GenerateMechanicalProfilePreviewRequest,
) -> MechanicalProfilePreviewGenerationResponse:
    skills = _hardware_skill_repo()
    repository = _mechanical_profile_repo()
    try:
        skills.migrate_legacy_rows()
        repository.seed_builtin_profiles()
        snapshot = repository.get(profile_id, revision=request.revision)
        records = repository.list_with_confirmed_hardware()
    except KeyError as exc:
        raise _mechanical_profile_error(
            404,
            "MECHANICAL_PROFILE_NOT_FOUND",
            "机械档案版本不存在，请刷新后重试。",
        ) from exc
    except (ValueError, ValidationError, HardwareSkillValidationError) as exc:
        raise _mechanical_profile_error(422, "MECHANICAL_PROFILE_INVALID", str(exc)) from exc

    record = next(
        (
            (candidate, hardware_ids, locked_ids)
            for candidate, hardware_ids, locked_ids in records
            if candidate.profile_id == snapshot.profile_id
            and candidate.revision == snapshot.revision
        ),
        None,
    )
    if record is None:
        raise _mechanical_profile_error(
            404,
            "MECHANICAL_PROFILE_NOT_FOUND",
            "机械档案版本不存在，请刷新后重试。",
        )
    source = _mechanical_preview_source(skills, snapshot, record[1])
    if source is None:
        return MechanicalProfilePreviewGenerationResponse(
            profile=_mechanical_profile_summary(*record),
            generationSource="ENVELOPE_FALLBACK",
        )
    skill, hardware_id, mechanical_markdown = source
    current_profile = skill.mechanicalProfile or {}
    if current_profile.get("revision") != snapshot.revision:
        snapshot = repository.resolve_for_hardware(hardware_id)
        record = next(
            (
                item
                for item in repository.list_with_confirmed_hardware()
                if item[0].profile_id == snapshot.profile_id
                and item[0].revision == snapshot.revision
            ),
            None,
        )
        if record is None:
            raise _mechanical_profile_error(
                404,
                "MECHANICAL_PROFILE_NOT_FOUND",
                "机械档案已更新，请刷新后重试。",
            )
    try:
        description = extract_mechanical_natural_description(mechanical_markdown)
        source_sha256 = mechanical_description_sha256(description)
    except MechanicalPreviewSourceError as exc:
        raise _mechanical_profile_error(
            422,
            "MECHANICAL_PREVIEW_DESCRIPTION_INVALID",
            str(exc),
        ) from exc

    geometry = snapshot.preview_geometry
    if geometry is not None and geometry.source_sha256 == source_sha256:
        return MechanicalProfilePreviewGenerationResponse(
            profile=_mechanical_profile_summary(*record),
            generationSource="DESCRIPTION_CACHE",
        )

    try:
        config, api_key = _llm_config()
        geometry = await MechanicalDescriptionPreviewService(provider_factory()).generate(
            description=description,
            config=config,
            api_key=api_key,
            model=config.defaultModel,
        )
        updated_markdown = write_preview_geometry(mechanical_markdown, geometry)
        skills.update_files(
            skill.skillName,
            updates=[("references/mechanical.md", updated_markdown)],
            expected_revision=skill.revision,
        )
        updated_snapshot = repository.resolve_for_hardware(hardware_id)
        updated_record = next(
            (
                item
                for item in repository.list_with_confirmed_hardware()
                if item[0].profile_id == updated_snapshot.profile_id
                and item[0].revision == updated_snapshot.revision
            ),
            None,
        )
        if updated_record is None:
            raise HardwareSkillValidationError("生成后的机械档案投影不存在。")
    except StructuredLLMError as exc:
        raise llm_http_exception(exc) from exc
    except HardwareSkillConflictError as exc:
        raise _mechanical_profile_error(
            409,
            "HARDWARE_SKILL_CONFLICT",
            "Hardware Skill 已更新，请刷新机械档案后重试。",
        ) from exc
    except (MechanicalPreviewSourceError, HardwareSkillValidationError, ValueError) as exc:
        raise _mechanical_profile_error(
            422,
            "MECHANICAL_PREVIEW_GENERATION_INVALID",
            str(exc),
        ) from exc
    return MechanicalProfilePreviewGenerationResponse(
        profile=_mechanical_profile_summary(*updated_record),
        generationSource="DESCRIPTION_GENERATED",
    )


@router.put(
    "/{component_id}/mechanical-profile-link",
    response_model=MechanicalProfileLinkResponse,
)
async def confirm_mechanical_profile_link(
    component_id: str,
    request: ConfirmMechanicalProfileLinkRequest,
) -> MechanicalProfileLinkResponse:
    repository = _mechanical_profile_repo()
    try:
        repository.seed_builtin_profiles()
        snapshot = repository.confirm_hardware_link(
            component_id,
            profile_id=request.profileId,
            revision=request.revision,
        )
    except KeyError as exc:
        code = (
            "COMPONENT_NOT_FOUND"
            if "hardware component" in str(exc)
            else "MECHANICAL_PROFILE_NOT_FOUND"
        )
        raise _mechanical_profile_error(404, code, str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise _mechanical_profile_error(422, "MECHANICAL_PROFILE_INVALID", str(exc)) from exc
    return MechanicalProfileLinkResponse(
        hardwareId=component_id,
        profileId=snapshot.profile_id,
        revision=snapshot.revision,
        confirmed=True,
    )


@router.delete(
    "/{component_id}/mechanical-profile-link",
    response_model=RemoveMechanicalProfileLinkResponse,
)
async def remove_mechanical_profile_link(
    component_id: str,
) -> RemoveMechanicalProfileLinkResponse:
    repository = _mechanical_profile_repo()
    try:
        removed = repository.remove_hardware_link(component_id)
    except ValueError as exc:
        raise _mechanical_profile_error(409, "MECHANICAL_PROFILE_LINK_LOCKED", str(exc)) from exc
    return RemoveMechanicalProfileLinkResponse(hardwareId=component_id, removed=removed)


@router.get("/board-profiles", response_model=BoardProfileListResponse)
async def list_board_profiles() -> BoardProfileListResponse:
    return BoardProfileListResponse(
        profiles=BoardProfileRepository(settings.data_dir).list_profiles()
    )


@router.get("/board-profiles/{profile_id}", response_model=BoardProfileResponse)
async def get_board_profile(profile_id: str) -> BoardProfileResponse:
    try:
        profile = BoardProfileRepository(settings.data_dir).get_profile(profile_id)
    except BoardProfileNotFoundError as exc:
        raise _board_profile_error(404, "BOARD_PROFILE_NOT_FOUND", str(exc)) from exc
    except BoardProfileValidationError as exc:
        raise _board_profile_error(422, "BOARD_PROFILE_INVALID", str(exc)) from exc
    return BoardProfileResponse(profile=profile)


@router.put("/board-profiles/{profile_id}", response_model=BoardProfileResponse)
async def update_board_profile(
    profile_id: str,
    request: UpdateBoardProfileRequest,
) -> BoardProfileResponse:
    try:
        profile = BoardProfileRepository(settings.data_dir).update_profile(
            profile_id,
            content=request.content,
            expected_revision=request.expectedRevision,
        )
    except BoardProfileConflictError as exc:
        raise _board_profile_error(409, "BOARD_PROFILE_CONFLICT", str(exc)) from exc
    except BoardProfileNotFoundError as exc:
        raise _board_profile_error(404, "BOARD_PROFILE_NOT_FOUND", str(exc)) from exc
    except BoardProfileValidationError as exc:
        raise _board_profile_error(422, "BOARD_PROFILE_INVALID", str(exc)) from exc
    return BoardProfileResponse(profile=profile)


@router.post("/board-profiles/{profile_id}/reset", response_model=BoardProfileResponse)
async def reset_board_profile(
    profile_id: str,
    request: ResetBoardProfileRequest,
) -> BoardProfileResponse:
    try:
        profile = BoardProfileRepository(settings.data_dir).reset_profile(
            profile_id,
            expected_revision=request.expectedRevision,
        )
    except BoardProfileConflictError as exc:
        raise _board_profile_error(409, "BOARD_PROFILE_CONFLICT", str(exc)) from exc
    except BoardProfileNotFoundError as exc:
        raise _board_profile_error(404, "BOARD_PROFILE_NOT_FOUND", str(exc)) from exc
    return BoardProfileResponse(profile=profile)


@router.get("/skills", response_model=HardwareSkillListResponse)
async def list_hardware_skills() -> HardwareSkillListResponse:
    try:
        skills = await asyncio.to_thread(
            lambda: _hardware_skill_repo().list_skills()
        )
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_SKILL_INVALID", str(exc)) from exc
    return HardwareSkillListResponse(skills=skills)


@router.post("/catalog/refresh", response_model=HardwareCatalogRefreshResponse)
async def refresh_hardware_catalog() -> HardwareCatalogRefreshResponse:
    try:
        candidates = await asyncio.to_thread(
            _hardware_skill_repo().refresh_active_catalog
        )
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_SKILL_INVALID", str(exc)) from exc
    return HardwareCatalogRefreshResponse(
        skills=[candidate.summary for candidate in candidates],
        refreshedAt=datetime.now(UTC).isoformat(),
    )


@router.get("/skills/{skill_name}", response_model=HardwareSkillResponse)
async def get_hardware_skill(skill_name: str) -> HardwareSkillResponse:
    try:
        skill = await asyncio.to_thread(
            _hardware_skill_repo().get_skill,
            skill_name,
        )
    except HardwareSkillNotFoundError as exc:
        raise _hardware_skill_error(404, "HARDWARE_SKILL_NOT_FOUND", str(exc)) from exc
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_SKILL_INVALID", str(exc)) from exc
    return HardwareSkillResponse(skill=skill)


@router.get("/skills/{skill_name}/media/{asset_name}")
async def get_hardware_skill_media(
    skill_name: str,
    asset_name: str,
) -> Response:
    try:
        media, payload = await asyncio.to_thread(
            _hardware_skill_repo().read_media,
            skill_name,
            asset_name,
        )
    except HardwareSkillNotFoundError as exc:
        raise _hardware_skill_error(404, "HARDWARE_MEDIA_NOT_FOUND", str(exc)) from exc
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_MEDIA_INVALID", str(exc)) from exc
    return Response(
        content=payload,
        media_type=media.contentType,
        headers={
            "Cache-Control": "private, max-age=86400",
            "ETag": f'"{media.sha256}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.put("/skills/{skill_name}/files", response_model=HardwareSkillResponse)
async def update_hardware_skill_file(
    skill_name: str,
    request: UpdateHardwareSkillFileRequest,
) -> HardwareSkillResponse:
    try:
        skill = await asyncio.to_thread(
            _hardware_skill_repo().update_file,
            skill_name,
            path=request.path,
            content=request.content,
            expected_revision=request.expectedRevision,
        )
    except HardwareSkillConflictError as exc:
        raise _hardware_skill_error(409, "HARDWARE_SKILL_CONFLICT", str(exc)) from exc
    except HardwareSkillNotFoundError as exc:
        raise _hardware_skill_error(404, "HARDWARE_SKILL_NOT_FOUND", str(exc)) from exc
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_SKILL_INVALID", str(exc)) from exc
    return HardwareSkillResponse(skill=skill)


@router.put("/skills/{skill_name}/files/batch", response_model=HardwareSkillResponse)
async def update_hardware_skill_files(
    skill_name: str,
    request: UpdateHardwareSkillFilesRequest,
) -> HardwareSkillResponse:
    try:
        skill = await asyncio.to_thread(
            _hardware_skill_repo().update_files,
            skill_name,
            updates=[(update.path, update.content) for update in request.updates],
            expected_revision=request.expectedRevision,
        )
    except HardwareSkillConflictError as exc:
        raise _hardware_skill_error(409, "HARDWARE_SKILL_CONFLICT", str(exc)) from exc
    except HardwareSkillNotFoundError as exc:
        raise _hardware_skill_error(404, "HARDWARE_SKILL_NOT_FOUND", str(exc)) from exc
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_SKILL_INVALID", str(exc)) from exc
    return HardwareSkillResponse(skill=skill)


@router.post(
    "/skills/drafts",
    response_model=HardwareSkillDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_hardware_skill_draft(
    request: CreateHardwareSkillDraftRequest,
) -> HardwareSkillDraftResponse:
    try:
        draft = _hardware_skill_repo().create_draft(
            name=request.name,
            description=request.description,
            sources=request.sources,
        )
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_SKILL_SOURCE_INVALID", str(exc)) from exc
    return HardwareSkillDraftResponse(draft=draft)


@router.post(
    "/skills/drafts/{draft_id}/messages",
    response_model=HardwareSkillDraftResponse,
)
async def continue_hardware_skill_draft(
    draft_id: str,
    request: ContinueHardwareSkillDraftRequest,
) -> HardwareSkillDraftResponse:
    try:
        draft = _hardware_skill_repo().continue_draft(
            draft_id,
            message=request.message,
            expected_revision=request.expectedRevision,
        )
    except HardwareSkillConflictError as exc:
        raise _hardware_skill_error(409, "HARDWARE_SKILL_DRAFT_CONFLICT", str(exc)) from exc
    except HardwareSkillNotFoundError as exc:
        raise _hardware_skill_error(404, "HARDWARE_SKILL_DRAFT_NOT_FOUND", str(exc)) from exc
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_SKILL_DRAFT_INVALID", str(exc)) from exc
    return HardwareSkillDraftResponse(draft=draft)


@router.post(
    "/skills/drafts/{draft_id}/confirm",
    response_model=HardwareSkillResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_hardware_skill_draft(
    draft_id: str,
    request: ConfirmHardwareSkillDraftRequest,
) -> HardwareSkillResponse:
    try:
        skill = _hardware_skill_repo().confirm_draft(
            draft_id,
            expected_revision=request.expectedRevision,
        )
    except HardwareSkillConflictError as exc:
        raise _hardware_skill_error(409, "HARDWARE_SKILL_DRAFT_CONFLICT", str(exc)) from exc
    except HardwareSkillNotFoundError as exc:
        raise _hardware_skill_error(404, "HARDWARE_SKILL_DRAFT_NOT_FOUND", str(exc)) from exc
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_SKILL_DRAFT_INVALID", str(exc)) from exc
    return HardwareSkillResponse(skill=skill)


@router.delete(
    "/skills/drafts/{draft_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_hardware_skill_draft(draft_id: str) -> Response:
    try:
        _hardware_skill_repo().delete_draft(draft_id)
    except HardwareSkillNotFoundError as exc:
        raise _hardware_skill_error(404, "HARDWARE_SKILL_DRAFT_NOT_FOUND", str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=ComponentListResponse)
async def list_components(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    include_archived: bool = Query(False),
) -> ComponentListResponse:
    repo = _repo()
    try:
        components = await asyncio.to_thread(
            repo.list_components,
            category=category,
            search=search,
            include_archived=include_archived,
        )
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_SKILL_INVALID", str(exc)) from exc
    return ComponentListResponse(components=components)


@router.get(
    "/components/{component_id}/package",
    response_model=HardwareComponentPackageResponse,
)
async def get_component_package(
    component_id: str,
) -> HardwareComponentPackageResponse:
    try:
        detail = _hardware_skill_repo().get_active_by_component_id(component_id)
    except HardwareSkillNotFoundError as exc:
        raise _hardware_skill_error(
            404,
            "HARDWARE_COMPONENT_PACKAGE_NOT_FOUND",
            str(exc),
        ) from exc
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(
            422,
            "HARDWARE_COMPONENT_PACKAGE_INVALID",
            str(exc),
        ) from exc
    current_files = {file.path: file for file in detail.files}
    legacy_paths = (
        ("README.md", "SKILL.md", "器件概览", "entry"),
        ("docs/specifications.md", "references/specifications.md", "技术规格", "reference"),
        ("docs/integration.md", "references/integration.md", "集成指南", "reference"),
        ("docs/safety.md", "references/safety.md", "安全说明", "reference"),
    )
    package = HardwareComponentPackageDetail(
        componentId=detail.componentId,
        componentName=detail.displayName,
        revision=detail.revision,
        files=[
            HardwareComponentPackageFile(
                path=legacy_path,
                title=title,
                kind=kind,
                content=current_files[skill_path].content,
                overridden=False,
            )
            for legacy_path, skill_path, title, kind in legacy_paths
        ],
    )
    return HardwareComponentPackageResponse(package=package)


@router.put(
    "/components/{component_id}/package/files",
    response_model=HardwareComponentPackageResponse,
)
async def update_component_package_file(
    component_id: str,
    request: UpdateHardwareComponentPackageFileRequest,
) -> HardwareComponentPackageResponse:
    del component_id, request
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "code": "HARDWARE_COMPONENT_PACKAGE_READ_ONLY",
            "message": "旧器件 Markdown 接口已改为只读，请使用 Hardware Skill 项目编辑器。",
            "retryable": False,
        },
    )


@router.get("/{component_id}", response_model=ComponentResponse)
async def get_component(component_id: str) -> ComponentResponse:
    repo = _repo()
    try:
        component = repo.get_component(component_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={
            "code": "COMPONENT_NOT_FOUND",
            "message": str(exc),
            "retryable": False,
        }) from exc
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_SKILL_INVALID", str(exc)) from exc
    return ComponentResponse(component=component)


@router.post("", response_model=ComponentResponse, status_code=201)
async def create_component(request: CreateComponentRequest) -> ComponentResponse:
    if request.category == HardwareCategory.MCU:
        raise _hardware_skill_error(
            422,
            "UNSUPPORTED_CONTROLLER_BOARD",
            "掌问只允许 K10 与 XIAO ESP32S3 Sense 两种主控，不能创建第三种主控。",
        )
    repo = _repo()
    try:
        component = repo.create_component(
            name=request.name,
            category=request.category.value,
            electrical=request.electrical,
            stock=request.stock,
            price=request.price,
            age_recommendation=request.ageRecommendation,
            safety_tags=request.safetyTags,
            notes=request.notes,
        )
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_SKILL_INVALID", str(exc)) from exc
    return ComponentResponse(component=component)


@router.put("/{component_id}", response_model=ComponentResponse)
async def update_component(
    component_id: str,
    request: UpdateComponentRequest,
) -> ComponentResponse:
    repo = _repo()
    try:
        component = repo.update_component(
            component_id,
            name=request.name,
            category=request.category.value if request.category else None,
            electrical=request.electrical,
            stock=request.stock,
            price=request.price,
            age_recommendation=request.ageRecommendation,
            safety_tags=request.safetyTags,
            notes=request.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={
            "code": "COMPONENT_NOT_FOUND",
            "message": str(exc),
            "retryable": False,
        }) from exc
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_SKILL_INVALID", str(exc)) from exc
    return ComponentResponse(component=component)


@router.delete("/{component_id}", response_model=ComponentResponse)
async def archive_component(component_id: str) -> ComponentResponse:
    repo = _repo()
    try:
        component = repo.archive_component(component_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={
            "code": "COMPONENT_NOT_FOUND",
            "message": str(exc),
            "retryable": False,
        }) from exc
    except HardwareSkillValidationError as exc:
        raise _hardware_skill_error(422, "HARDWARE_SKILL_INVALID", str(exc)) from exc
    return ComponentResponse(component=component)


@router.post("/validate", response_model=ValidateCombinationResponse)
async def validate_combination(
    request: ValidateCombinationRequest,
) -> ValidateCombinationResponse:
    return ValidateCombinationResponse(
        result=validate_component_ids(request.componentIds)
    )


def validate_component_ids(component_ids: list[str]) -> ValidationResult:
    """Shared validation entry point for solution generation."""
    skill_repo = _hardware_skill_repo()
    components = []
    rules = []
    missing_ids = []
    for cid in component_ids:
        try:
            detail = skill_repo.ensure_component_migrated(cid)
            component = skill_repo.component_from_detail(detail)
            if (
                component.category == HardwareCategory.MCU
                and component.id not in SUPPORTED_CONTROLLER_COMPONENT_IDS
            ):
                missing_ids.append(cid)
                continue
            components.append(component)
            rules.extend(detail.rules)
        except (HardwareSkillNotFoundError, HardwareSkillValidationError):
            missing_ids.append(cid)

    result = validate_components(components, rules=rules)
    if missing_ids:
        result.checks.append(
            ValidationCheck(
                dimension="component_exists",
                severity=ValidationSeverity.FAIL,
                message="存在未找到的硬件组件。",
                details=", ".join(missing_ids),
            )
        )
        result.overall = ValidationSeverity.FAIL
        result.message = "硬件组合校验未通过，请先处理失败项。"
    return result


def _repo() -> HardwareRepository:
    project_repo = ProjectRepository(settings.data_dir)
    repo = HardwareRepository(project_repo.db_path, data_dir=settings.data_dir)
    seed_default_components(project_repo.db_path)
    HardwareSkillRepository(settings.data_dir, project_repo.db_path).install_bundled_catalog()
    return repo


def _hardware_skill_repo() -> HardwareSkillRepository:
    project_repo = ProjectRepository(settings.data_dir)
    seed_default_components(project_repo.db_path)
    repository = HardwareSkillRepository(settings.data_dir, project_repo.db_path)
    repository.install_bundled_catalog()
    return repository


def _mechanical_profile_repo() -> MechanicalProfileRepository:
    project_repo = ProjectRepository(settings.data_dir)
    seed_default_components(project_repo.db_path)
    return MechanicalProfileRepository(project_repo.db_path)


def _mechanical_profile_summary(
    snapshot: MechanicalProfileSnapshot,
    hardware_ids: tuple[str, ...],
    locked_ids: tuple[str, ...],
) -> MechanicalProfileSummary:
    return MechanicalProfileSummary(
        profileId=snapshot.profile_id,
        revision=snapshot.revision,
        displayName=snapshot.display_name,
        category=snapshot.category,
        dimensions=snapshot.dimensions.model_dump(mode="json"),
        mountingMode=snapshot.mounting.mode,
        mountingStrategy=snapshot.mounting.strategy.value,
        preferredSurface=snapshot.mounting.preferred_surface.value,
        allowedSurfaces=[item.value for item in snapshot.mounting.allowed_enclosure_surfaces],
        clearance=snapshot.mounting.clearance,
        evidenceLevel=snapshot.evidence_level,
        representation=snapshot.representation,
        coordinateSystem=snapshot.coordinate_system.model_dump(mode="json"),
        modelKind=snapshot.model_kind.value,
        previewGeometry=(
            snapshot.preview_geometry.model_dump(mode="json")
            if snapshot.preview_geometry is not None
            else None
        ),
        mountingHoles=[item.model_dump(mode="json") for item in snapshot.mounting.holes],
        openings=[item.model_dump(mode="json") for item in snapshot.openings],
        keepouts=[item.model_dump(mode="json") for item in snapshot.keepouts],
        contentSha256=snapshot.content_sha256,
        confirmedHardwareIds=list(hardware_ids),
        lockedHardwareIds=list(locked_ids),
    )


def _mechanical_preview_source(
    skills: HardwareSkillRepository,
    snapshot: MechanicalProfileSnapshot,
    hardware_ids: tuple[str, ...],
):
    for hardware_id in hardware_ids:
        try:
            detail = skills.get_active_by_component_id(hardware_id)
        except (HardwareSkillNotFoundError, HardwareSkillValidationError):
            continue
        profile = detail.mechanicalProfile or {}
        if profile.get("profile_id") != snapshot.profile_id:
            continue
        mechanical_file = next(
            (
                file
                for file in detail.files
                if file.path == "references/mechanical.md"
            ),
            None,
        )
        if mechanical_file is not None:
            return detail, hardware_id, mechanical_file.content
    return None


def _llm_config():
    return require_llm_config(
        data_dir=settings.data_dir,
        credential_store=credential_store_factory(),
        credential_service=settings.credential_service,
        credential_account=settings.credential_account,
        workload=ModelWorkload.ENGINEERING,
    )


def _mechanical_profile_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "retryable": False},
    )


def _board_profile_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "retryable": status_code == 409},
    )


def _hardware_skill_error(
    status_code: int,
    code: str,
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "retryable": status_code == 409},
    )

"""Classroom-scoped API that never relaxes the generic Project owner middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import Field

from zhangwen.config import settings
from zhangwen.devices.router import get_device_operation_service
from zhangwen.host import require_desktop_host
from zhangwen.creator.repository import CreatorError, CreatorRepository
from zhangwen.domains.classroom.models import (
    Assignment,
    AssignmentCollaborationMode,
    ClassGroup,
    ClassMembership,
    ClassMembershipRole,
    ClassroomAssignmentDetail,
    ClassroomClassDetail,
    ClassroomHome,
    ClassroomProposalWorkspace,
    ClassroomWorkOverview,
    Course,
    Organization,
    ProcessJournalEntry,
    ProcessJournalEntryKind,
    ProjectProposalContentV2,
    ProjectProposalSourceKind,
    CheckpointReviewDecision,
    ProjectCheckpointKind,
    ProjectLearningModel,
    RubricDimension,
    StructurePolicy,
    WorkLearningBinding,
    WorkMembership,
    WorkMembershipRole,
)
from zhangwen.domains.classroom.proposal_service import ClassroomProposalService
from zhangwen.domains.classroom.repository import (
    ClassroomAuthorizationError,
    ClassroomConflictError,
    ClassroomError,
    ClassroomNotFoundError,
    ClassroomRepository,
)
from zhangwen.domains.simulation.models import SimulationProjectDraft, SimulationWorkspace
from zhangwen.domains.simulation.qemu import EspressifQemuPackage, EspressifQemuStatus
from zhangwen.domains.simulation.run_models import (
    SimulationRunRecord,
    SimulationRunRequest,
    SimulationRunWorkspace,
)
from zhangwen.domains.simulation.runner import SimulationRunService
from zhangwen.domains.simulation.runtime.manifest import SimulationRuntimePackage
from zhangwen.domains.simulation.runtime.models import (
    RuntimeEngineMode,
    SimulationRuntimeStatus,
)
from zhangwen.domains.simulation.service import SimulationProjectService
from zhangwen.domains.deployment.models import (
    ConnectProjectDeviceRequest,
    CreateDeploymentBundleRequest,
    DeploymentBundle,
    DeploymentWorkspace,
    PhysicalObservation,
    PhysicalObservationRequest,
    ProjectDeviceConnection,
    ProjectDeviceDeployment,
    StartProjectDeploymentRequest,
)
from zhangwen.domains.deployment.service import (
    ProjectDeploymentError,
    ProjectDeploymentService,
)
from zhangwen.domains.making.models import (
    AssemblyRecord,
    BuildRouteDecisionRecord,
    ChooseBuildRouteRequest,
    CreateStructureRevisionRequest,
    MakingWorkspace,
    RecordAssemblyRequest,
    StructureRevisionRecord,
)
from zhangwen.domains.making.service import MakingError, ProjectMakingService
from zhangwen.domains.submission.models import (
    ApplySyncBatchRequest,
    ApplySyncBatchResult,
    AssignmentProgressOverview,
    CopyAssignmentRequest,
    CourseExportBundle,
    CreateSubmissionDraftRequest,
    EvidenceResetRecord,
    EvidenceResetRequest,
    ProjectSubmissionWorkspace,
    RecordContributionRequest,
    ReviewSubmissionRequest,
    ReviewSubmissionResult,
    SubmissionRevisionRecord,
    SubmitSubmissionRequest,
    TeamContributionRecord,
)
from zhangwen.domains.submission.service import (
    ClassroomPortfolioService,
    ProjectSubmissionError,
    ProjectSubmissionService,
)
from zhangwen.proposals.models import ProposalExportFormat


router = APIRouter(prefix="/api/classroom", tags=["classroom"])
T = TypeVar("T")


class CreateOrganizationRequest(ProjectLearningModel):
    name: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)


class OrganizationResponse(ProjectLearningModel):
    organization: Organization


class CreateCourseRequest(ProjectLearningModel):
    title: str = Field(min_length=1, max_length=240)
    code: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=12000)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)


class CourseResponse(ProjectLearningModel):
    course: Course


class CreateClassRequest(ProjectLearningModel):
    title: str = Field(min_length=1, max_length=240)
    term: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)


class ClassResponse(ProjectLearningModel):
    class_group: ClassGroup = Field(alias="classGroup")


class AddClassMemberRequest(ProjectLearningModel):
    subject: str = Field(min_length=1, max_length=300)
    role: ClassMembershipRole


class ClassMemberResponse(ProjectLearningModel):
    membership: ClassMembership


class CreateAssignmentRequest(ProjectLearningModel):
    title: str = Field(min_length=1, max_length=240)
    driving_question: str = Field(alias="drivingQuestion", min_length=1, max_length=4000)
    description: str = Field(default="", max_length=12000)
    collaboration_mode: AssignmentCollaborationMode = Field(alias="collaborationMode")
    structure_policy: StructurePolicy = Field(alias="structurePolicy")
    allowed_chip_targets: list[str] = Field(alias="allowedChipTargets", min_length=1)
    required_checkpoints: list[ProjectCheckpointKind] = Field(
        alias="requiredCheckpoints", min_length=1
    )
    safety_rules: list[str] = Field(alias="safetyRules", min_length=1)
    submission_requirements: list[str] = Field(
        alias="submissionRequirements", default_factory=list
    )
    rubric_dimensions: list[RubricDimension] = Field(
        alias="rubricDimensions", min_length=1
    )
    due_at: str | None = Field(alias="dueAt", default=None)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)


class AssignmentResponse(ProjectLearningModel):
    assignment: Assignment


class CreateAssignmentWorkRequest(ProjectLearningModel):
    name: str = Field(min_length=1, max_length=240)
    initial_idea: str = Field(alias="initialIdea", min_length=1, max_length=4000)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)


class AssignmentWorkResponse(ProjectLearningModel):
    work: WorkLearningBinding


class AddWorkMemberRequest(ProjectLearningModel):
    subject: str = Field(min_length=1, max_length=300)
    role: WorkMembershipRole


class WorkMemberResponse(ProjectLearningModel):
    membership: WorkMembership


class AppendJournalRequest(ProjectLearningModel):
    kind: ProcessJournalEntryKind
    title: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=12000)
    related_kind: str | None = Field(alias="relatedKind", default=None, max_length=120)
    related_id: str | None = Field(alias="relatedId", default=None, max_length=300)


class JournalEntryResponse(ProjectLearningModel):
    entry: ProcessJournalEntry


class JournalResponse(ProjectLearningModel):
    entries: list[ProcessJournalEntry]


class WorkOverviewResponse(ProjectLearningModel):
    work: ClassroomWorkOverview


class CreateProposalRevisionRequest(ProjectLearningModel):
    content: ProjectProposalContentV2
    source_kind: ProjectProposalSourceKind = Field(alias="sourceKind")
    source_proposal_id: str | None = Field(alias="sourceProposalId", default=None)
    base_revision_id: str | None = Field(alias="baseRevisionId", default=None)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=80)


class AnswerFacilitatorRequest(ProjectLearningModel):
    answer: str = Field(min_length=1, max_length=12000)
    base_revision_id: str | None = Field(alias="baseRevisionId", default=None)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=80)


class ImportLegacyProposalRequest(ProjectLearningModel):
    legacy_proposal_id: str = Field(alias="legacyProposalId", min_length=1, max_length=300)
    base_revision_id: str | None = Field(alias="baseRevisionId", default=None)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=80)


class ReviewProposalRequest(ProjectLearningModel):
    decision: CheckpointReviewDecision
    comment: str = Field(min_length=1, max_length=12000)


class CreateSimulationDraftRequest(ProjectLearningModel):
    board_package_revision_id: str = Field(
        alias="boardPackageRevisionId", min_length=1, max_length=200
    )
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=80)


class UpdateSimulationDraftRequest(ProjectLearningModel):
    draft: SimulationProjectDraft
    base_draft_revision: int = Field(alias="baseDraftRevision", ge=1)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=80)


class SaveSimulationRevisionRequest(ProjectLearningModel):
    base_draft_revision: int = Field(alias="baseDraftRevision", ge=1)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=80)


class ImportWokwiSimulationRequest(ProjectLearningModel):
    diagram_json: str = Field(alias="diagramJson", min_length=1, max_length=524288)
    base_draft_revision: int = Field(alias="baseDraftRevision", ge=1)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=80)


class StartSimulationRunRequest(ProjectLearningModel):
    simulation_project_revision_id: str = Field(
        alias="simulationProjectRevisionId", min_length=1, max_length=300
    )
    engine_mode: RuntimeEngineMode = Field(alias="engineMode")
    reflections: dict[str, str] = Field(default_factory=dict)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=80)


@router.get("/home", response_model=ClassroomHome)
async def get_classroom_home() -> ClassroomHome:
    return _call(lambda repository: repository.get_home())


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(payload: CreateOrganizationRequest) -> OrganizationResponse:
    organization = _call(
        lambda repository: repository.create_organization(
            name=payload.name,
            idempotency_key=payload.idempotency_key,
        )
    )
    return OrganizationResponse(organization=organization)


@router.post(
    "/organizations/{organization_id}/courses",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_course(
    organization_id: str, payload: CreateCourseRequest
) -> CourseResponse:
    course = _call(
        lambda repository: repository.create_course(
            organization_id=organization_id,
            title=payload.title,
            code=payload.code,
            description=payload.description,
            idempotency_key=payload.idempotency_key,
        )
    )
    return CourseResponse(course=course)


@router.post(
    "/courses/{course_id}/classes",
    response_model=ClassResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_class_group(
    course_id: str, payload: CreateClassRequest
) -> ClassResponse:
    class_group = _call(
        lambda repository: repository.create_class_group(
            course_id=course_id,
            title=payload.title,
            term=payload.term,
            idempotency_key=payload.idempotency_key,
        )
    )
    return ClassResponse(classGroup=class_group)


@router.get("/classes/{class_group_id}", response_model=ClassroomClassDetail)
async def get_class_group(class_group_id: str) -> ClassroomClassDetail:
    return _call(lambda repository: repository.get_class_detail(class_group_id))


@router.post(
    "/classes/{class_group_id}/members",
    response_model=ClassMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_class_member(
    class_group_id: str, payload: AddClassMemberRequest
) -> ClassMemberResponse:
    membership = _call(
        lambda repository: repository.add_class_member(
            class_group_id=class_group_id,
            subject=payload.subject,
            role=payload.role,
        )
    )
    return ClassMemberResponse(membership=membership)


@router.post(
    "/classes/{class_group_id}/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment(
    class_group_id: str, payload: CreateAssignmentRequest
) -> AssignmentResponse:
    assignment = _call(
        lambda repository: repository.create_assignment(
            class_group_id=class_group_id,
            title=payload.title,
            driving_question=payload.driving_question,
            description=payload.description,
            collaboration_mode=payload.collaboration_mode,
            structure_policy=payload.structure_policy,
            allowed_chip_targets=payload.allowed_chip_targets,
            required_checkpoints=payload.required_checkpoints,
            safety_rules=payload.safety_rules,
            submission_requirements=payload.submission_requirements,
            rubric_dimensions=payload.rubric_dimensions,
            due_at=payload.due_at,
            idempotency_key=payload.idempotency_key,
        )
    )
    return AssignmentResponse(assignment=assignment)


@router.get(
    "/assignments/{assignment_id}", response_model=ClassroomAssignmentDetail
)
async def get_assignment(assignment_id: str) -> ClassroomAssignmentDetail:
    return _call(lambda repository: repository.get_assignment_detail(assignment_id))


@router.post(
    "/assignments/{assignment_id}/works",
    response_model=AssignmentWorkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment_work(
    assignment_id: str, payload: CreateAssignmentWorkRequest
) -> AssignmentWorkResponse:
    try:
        assignment = _call(
            lambda repository: repository.get_assignment_detail(assignment_id)
        ).assignment
        created = CreatorRepository(settings.data_dir).create_work(
            name=payload.name,
            initial_idea=payload.initial_idea,
            idempotency_key=payload.idempotency_key,
            selected_hardware_ids=[],
        )
        binding = _call(
            lambda repository: repository.bind_work_to_assignment(
                assignment_id=assignment_id,
                work_id=created.work_id,
                collaboration_mode=assignment.collaboration_mode,
            )
        )
        return AssignmentWorkResponse(work=binding)
    except CreatorError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "retryable": False},
        ) from exc


@router.get("/works/{work_id}", response_model=WorkOverviewResponse)
async def get_work_overview(work_id: str) -> WorkOverviewResponse:
    return WorkOverviewResponse(
        work=_call(lambda repository: repository.get_work_overview(work_id))
    )


@router.post(
    "/works/{work_id}/members",
    response_model=WorkMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_work_member(
    work_id: str, payload: AddWorkMemberRequest
) -> WorkMemberResponse:
    membership = _call(
        lambda repository: repository.add_work_member(
            work_id=work_id, subject=payload.subject, role=payload.role
        )
    )
    return WorkMemberResponse(membership=membership)


@router.get("/works/{work_id}/journal", response_model=JournalResponse)
async def list_journal(work_id: str) -> JournalResponse:
    return JournalResponse(
        entries=_call(lambda repository: repository.list_journal(work_id))
    )


@router.post(
    "/works/{work_id}/journal",
    response_model=JournalEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def append_journal(
    work_id: str, payload: AppendJournalRequest
) -> JournalEntryResponse:
    entry = _call(
        lambda repository: repository.append_journal_entry(
            work_id=work_id,
            kind=payload.kind,
            title=payload.title,
            body=payload.body,
            related_kind=payload.related_kind,
            related_id=payload.related_id,
        )
    )
    return JournalEntryResponse(entry=entry)


@router.get(
    "/works/{work_id}/proposal-workspace",
    response_model=ClassroomProposalWorkspace,
)
async def get_proposal_workspace(work_id: str) -> ClassroomProposalWorkspace:
    return _call(lambda _: ClassroomProposalService(settings.data_dir).get_workspace(work_id))


@router.post(
    "/works/{work_id}/proposal-revisions",
    response_model=ClassroomProposalWorkspace,
)
async def create_proposal_revision(
    work_id: str, payload: CreateProposalRevisionRequest
) -> ClassroomProposalWorkspace:
    return _call(
        lambda _: ClassroomProposalService(settings.data_dir).create_revision(
            work_id=work_id,
            content=payload.content,
            source_kind=payload.source_kind,
            source_proposal_id=payload.source_proposal_id,
            base_revision_id=payload.base_revision_id,
            idempotency_key=payload.idempotency_key,
        )
    )


@router.post(
    "/works/{work_id}/proposal-facilitator/answer",
    response_model=ClassroomProposalWorkspace,
)
async def answer_proposal_facilitator(
    work_id: str, payload: AnswerFacilitatorRequest
) -> ClassroomProposalWorkspace:
    return _call(
        lambda _: ClassroomProposalService(settings.data_dir).answer_next_question(
            work_id=work_id,
            answer=payload.answer,
            base_revision_id=payload.base_revision_id,
            idempotency_key=payload.idempotency_key,
        )
    )


@router.post(
    "/works/{work_id}/proposal-revisions/import-legacy",
    response_model=ClassroomProposalWorkspace,
)
async def import_legacy_proposal(
    work_id: str, payload: ImportLegacyProposalRequest
) -> ClassroomProposalWorkspace:
    return _call(
        lambda _: ClassroomProposalService(settings.data_dir).import_legacy_proposal(
            work_id=work_id,
            legacy_proposal_id=payload.legacy_proposal_id,
            base_revision_id=payload.base_revision_id,
            idempotency_key=payload.idempotency_key,
        )
    )


@router.post(
    "/works/{work_id}/proposal-revisions/{revision_id}/student-confirm",
    response_model=ClassroomProposalWorkspace,
)
async def student_confirm_proposal(
    work_id: str, revision_id: str
) -> ClassroomProposalWorkspace:
    return _call(
        lambda _: ClassroomProposalService(settings.data_dir).student_confirm(
            work_id, revision_id
        )
    )


@router.post(
    "/works/{work_id}/proposal-revisions/{revision_id}/review",
    response_model=ClassroomProposalWorkspace,
)
async def review_proposal(
    work_id: str, revision_id: str, payload: ReviewProposalRequest
) -> ClassroomProposalWorkspace:
    return _call(
        lambda _: ClassroomProposalService(settings.data_dir).review_proposal(
            work_id=work_id,
            revision_id=revision_id,
            decision=payload.decision,
            comment=payload.comment,
        )
    )


@router.get(
    "/works/{work_id}/proposal-revisions/{revision_id}/export",
    response_class=Response,
)
async def export_proposal_revision(
    work_id: str,
    revision_id: str,
    format: ProposalExportFormat = Query(ProposalExportFormat.MARKDOWN),
) -> Response:
    exported = _call(
        lambda _: ClassroomProposalService(settings.data_dir).export_revision(
            work_id, revision_id, format.value
        )
    )
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'},
    )


@router.get(
    "/simulation/runtime-status",
    response_model=SimulationRuntimeStatus,
)
async def get_simulation_runtime_status() -> SimulationRuntimeStatus:
    return SimulationRuntimePackage.load_builtin().status(settings.data_dir)


@router.get(
    "/simulation/qemu-status",
    response_model=EspressifQemuStatus,
)
async def get_espressif_qemu_status() -> EspressifQemuStatus:
    return EspressifQemuPackage.load_builtin().status(settings.data_dir)


@router.get(
    "/works/{work_id}/simulation-workspace",
    response_model=SimulationWorkspace,
)
async def get_simulation_workspace(work_id: str) -> SimulationWorkspace:
    return _call(
        lambda _: SimulationProjectService(settings.data_dir).get_workspace(work_id)
    )


@router.post(
    "/works/{work_id}/simulation-draft",
    response_model=SimulationWorkspace,
)
async def create_simulation_draft(
    work_id: str, payload: CreateSimulationDraftRequest
) -> SimulationWorkspace:
    return _call(
        lambda _: SimulationProjectService(settings.data_dir).create_draft(
            work_id=work_id,
            board_package_revision_id=payload.board_package_revision_id,
            idempotency_key=payload.idempotency_key,
        )
    )


@router.put(
    "/works/{work_id}/simulation-draft",
    response_model=SimulationWorkspace,
)
async def update_simulation_draft(
    work_id: str, payload: UpdateSimulationDraftRequest
) -> SimulationWorkspace:
    return _call(
        lambda _: SimulationProjectService(settings.data_dir).update_draft(
            work_id=work_id,
            draft=payload.draft,
            base_draft_revision=payload.base_draft_revision,
            idempotency_key=payload.idempotency_key,
        )
    )


@router.post(
    "/works/{work_id}/simulation-revisions",
    response_model=SimulationWorkspace,
)
async def save_simulation_revision(
    work_id: str, payload: SaveSimulationRevisionRequest
) -> SimulationWorkspace:
    return _call(
        lambda _: SimulationProjectService(settings.data_dir).save_revision(
            work_id=work_id,
            base_draft_revision=payload.base_draft_revision,
            idempotency_key=payload.idempotency_key,
        )
    )


@router.post(
    "/works/{work_id}/simulation-import/wokwi",
    response_model=SimulationWorkspace,
)
async def import_wokwi_simulation(
    work_id: str, payload: ImportWokwiSimulationRequest
) -> SimulationWorkspace:
    return _call(
        lambda _: SimulationProjectService(settings.data_dir).import_wokwi_diagram(
            work_id=work_id,
            diagram_json=payload.diagram_json,
            base_draft_revision=payload.base_draft_revision,
            idempotency_key=payload.idempotency_key,
        )
    )


@router.get(
    "/works/{work_id}/simulation-runs",
    response_model=SimulationRunWorkspace,
)
async def get_simulation_runs(work_id: str) -> SimulationRunWorkspace:
    return _call(lambda _: SimulationRunService(settings.data_dir).get_workspace(work_id))


@router.post(
    "/works/{work_id}/simulation-runs",
    response_model=SimulationRunRecord,
)
async def start_simulation_run(
    work_id: str, payload: StartSimulationRunRequest
) -> SimulationRunRecord:
    request = SimulationRunRequest.model_validate(payload.model_dump(by_alias=True))
    return _call(
        lambda _: SimulationRunService(settings.data_dir).run(
            work_id=work_id,
            request=request,
        )
    )


@router.get(
    "/works/{work_id}/making-workspace",
    response_model=MakingWorkspace,
)
async def get_making_workspace(work_id: str) -> MakingWorkspace:
    return _making_call(
        lambda: ProjectMakingService(settings.data_dir).get_workspace(work_id)
    )


@router.post(
    "/works/{work_id}/build-route-decisions",
    response_model=BuildRouteDecisionRecord,
    status_code=status.HTTP_201_CREATED,
)
async def choose_project_build_route(
    work_id: str,
    payload: ChooseBuildRouteRequest,
) -> BuildRouteDecisionRecord:
    return _making_call(
        lambda: ProjectMakingService(settings.data_dir).choose_route(
            work_id=work_id, request=payload
        )
    )


@router.post(
    "/works/{work_id}/structure-revisions",
    response_model=StructureRevisionRecord,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_structure_revision(
    work_id: str,
    payload: CreateStructureRevisionRequest,
) -> StructureRevisionRecord:
    return _making_call(
        lambda: ProjectMakingService(settings.data_dir).create_structure_revision(
            work_id=work_id, request=payload
        )
    )


@router.post(
    "/works/{work_id}/assembly-records",
    response_model=AssemblyRecord,
    status_code=status.HTTP_201_CREATED,
)
async def record_project_assembly(
    work_id: str,
    payload: RecordAssemblyRequest,
) -> AssemblyRecord:
    return _making_call(
        lambda: ProjectMakingService(settings.data_dir).record_assembly(
            work_id=work_id, request=payload
        )
    )


@router.get(
    "/works/{work_id}/submission-workspace",
    response_model=ProjectSubmissionWorkspace,
)
async def get_submission_workspace(work_id: str) -> ProjectSubmissionWorkspace:
    return _submission_call(
        lambda: ProjectSubmissionService(settings.data_dir).get_workspace(work_id)
    )


@router.post(
    "/works/{work_id}/submission-drafts",
    response_model=SubmissionRevisionRecord,
    status_code=status.HTTP_201_CREATED,
)
async def create_submission_draft(
    work_id: str,
    payload: CreateSubmissionDraftRequest,
) -> SubmissionRevisionRecord:
    return _submission_call(
        lambda: ProjectSubmissionService(settings.data_dir).create_draft(
            work_id=work_id, request=payload
        )
    )


@router.post(
    "/works/{work_id}/submit",
    response_model=SubmissionRevisionRecord,
)
async def submit_project(
    work_id: str,
    payload: SubmitSubmissionRequest,
) -> SubmissionRevisionRecord:
    return _submission_call(
        lambda: ProjectSubmissionService(settings.data_dir).submit(
            work_id=work_id, request=payload
        )
    )


@router.post(
    "/works/{work_id}/reviews",
    response_model=ReviewSubmissionResult,
    status_code=status.HTTP_201_CREATED,
)
async def review_project_submission(
    work_id: str,
    payload: ReviewSubmissionRequest,
) -> ReviewSubmissionResult:
    return _submission_call(
        lambda: ProjectSubmissionService(settings.data_dir).review(
            work_id=work_id, request=payload
        )
    )


@router.post(
    "/works/{work_id}/contributions",
    response_model=TeamContributionRecord,
    status_code=status.HTTP_201_CREATED,
)
async def record_project_contribution(
    work_id: str,
    payload: RecordContributionRequest,
) -> TeamContributionRecord:
    return _submission_call(
        lambda: ProjectSubmissionService(settings.data_dir).record_contribution(
            work_id=work_id, request=payload
        )
    )


@router.post(
    "/works/{work_id}/evidence-resets",
    response_model=EvidenceResetRecord,
    status_code=status.HTTP_201_CREATED,
)
async def reset_project_physical_evidence(
    work_id: str,
    payload: EvidenceResetRequest,
) -> EvidenceResetRecord:
    return _submission_call(
        lambda: ProjectSubmissionService(settings.data_dir).reset_physical_evidence(
            work_id=work_id, request=payload
        )
    )


@router.post("/sync", response_model=ApplySyncBatchResult)
async def sync_classroom_operations(
    payload: ApplySyncBatchRequest,
) -> ApplySyncBatchResult:
    return _submission_call(
        lambda: ProjectSubmissionService(settings.data_dir).apply_sync_batch(payload)
    )


@router.get(
    "/assignments/{assignment_id}/progress",
    response_model=AssignmentProgressOverview,
)
async def get_assignment_progress(
    assignment_id: str,
) -> AssignmentProgressOverview:
    return _submission_call(
        lambda: ClassroomPortfolioService(settings.data_dir).get_assignment_progress(
            assignment_id
        )
    )


@router.get("/courses/{course_id}/export", response_model=CourseExportBundle)
async def export_classroom_course(course_id: str) -> CourseExportBundle:
    return _submission_call(
        lambda: ClassroomPortfolioService(settings.data_dir).export_course(course_id)
    )


@router.post(
    "/assignments/{assignment_id}/copy",
    response_model=Assignment,
    status_code=status.HTTP_201_CREATED,
)
async def copy_classroom_assignment(
    assignment_id: str,
    payload: CopyAssignmentRequest,
) -> Assignment:
    return _submission_call(
        lambda: ClassroomPortfolioService(settings.data_dir).copy_assignment(
            assignment_id, payload
        )
    )


@router.get(
    "/works/{work_id}/deployment-workspace",
    response_model=DeploymentWorkspace,
)
async def get_deployment_workspace(work_id: str) -> DeploymentWorkspace:
    return _deployment_call(
        lambda: ProjectDeploymentService(settings.data_dir).get_workspace(work_id)
    )


@router.post(
    "/works/{work_id}/deployment-bundles",
    response_model=DeploymentBundle,
    status_code=status.HTTP_201_CREATED,
)
async def create_deployment_bundle(
    work_id: str,
    payload: CreateDeploymentBundleRequest,
) -> DeploymentBundle:
    return _deployment_call(
        lambda: ProjectDeploymentService(settings.data_dir).create_bundle(
            work_id=work_id,
            request=payload,
        )
    )


@router.post(
    "/works/{work_id}/project-device-sessions",
    response_model=ProjectDeviceConnection,
)
async def connect_project_device(
    work_id: str,
    payload: ConnectProjectDeviceRequest,
    http_request: Request,
) -> ProjectDeviceConnection:
    require_desktop_host(http_request, "device_upload")
    return await _deployment_call_async(
        lambda: ProjectDeploymentService(
            settings.data_dir,
            device_service=get_device_operation_service(),
        ).connect_device(
            work_id=work_id,
            bundle_id=payload.deployment_bundle_id,
            port_id=payload.port_id,
        )
    )


@router.post(
    "/works/{work_id}/device-deployments",
    response_model=ProjectDeviceDeployment,
)
async def start_project_device_deployment(
    work_id: str,
    payload: StartProjectDeploymentRequest,
    http_request: Request,
) -> ProjectDeviceDeployment:
    require_desktop_host(http_request, "device_upload")
    return await _deployment_call_async(
        lambda: ProjectDeploymentService(
            settings.data_dir,
            device_service=get_device_operation_service(),
        ).start_deployment(work_id=work_id, request=payload)
    )


@router.get(
    "/works/{work_id}/device-deployments/{deployment_id}",
    response_model=ProjectDeviceDeployment,
)
async def get_project_device_deployment(
    work_id: str,
    deployment_id: str,
) -> ProjectDeviceDeployment:
    return _deployment_call(
        lambda: ProjectDeploymentService(
            settings.data_dir,
            device_service=get_device_operation_service(),
        ).reconcile_deployment(work_id, deployment_id)
    )


@router.post(
    "/works/{work_id}/device-deployments/{deployment_id}/cancel",
    response_model=ProjectDeviceDeployment,
)
async def cancel_project_device_deployment(
    work_id: str,
    deployment_id: str,
    http_request: Request,
) -> ProjectDeviceDeployment:
    require_desktop_host(http_request, "device_upload")
    return await _deployment_call_async(
        lambda: ProjectDeploymentService(
            settings.data_dir,
            device_service=get_device_operation_service(),
        ).cancel_deployment(work_id=work_id, deployment_id=deployment_id)
    )


@router.post(
    "/works/{work_id}/physical-observations",
    response_model=PhysicalObservation,
    status_code=status.HTTP_201_CREATED,
)
async def record_physical_observation(
    work_id: str,
    payload: PhysicalObservationRequest,
) -> PhysicalObservation:
    return _deployment_call(
        lambda: ProjectDeploymentService(settings.data_dir).record_physical_observation(
            work_id=work_id,
            request=payload,
        )
    )


def _deployment_call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ProjectDeploymentError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            },
        ) from exc


def _making_call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except MakingError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            },
        ) from exc
    except ClassroomError as exc:
        if isinstance(exc, ClassroomAuthorizationError):
            status_code = status.HTTP_403_FORBIDDEN
        elif isinstance(exc, ClassroomNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, ClassroomConflictError):
            status_code = status.HTTP_409_CONFLICT
        else:
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": getattr(exc, "code", "CLASSROOM_ERROR"),
                "message": str(exc),
                "retryable": False,
            },
        ) from exc


def _submission_call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ProjectSubmissionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            },
        ) from exc
    except ClassroomError as exc:
        if isinstance(exc, ClassroomAuthorizationError):
            status_code = status.HTTP_403_FORBIDDEN
        elif isinstance(exc, ClassroomNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, ClassroomConflictError):
            status_code = status.HTTP_409_CONFLICT
        else:
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": getattr(exc, "code", "CLASSROOM_ERROR"),
                "message": str(exc),
                "retryable": False,
            },
        ) from exc


async def _deployment_call_async(operation: Callable[[], Awaitable[T]]) -> T:
    try:
        return await operation()
    except ProjectDeploymentError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            },
        ) from exc


def _call(operation: Callable[[ClassroomRepository], T]) -> T:
    try:
        return operation(ClassroomRepository(settings.data_dir))
    except ClassroomError as exc:
        code = getattr(exc, "code", "CLASSROOM_ERROR")
        if isinstance(exc, ClassroomAuthorizationError):
            status_code = status.HTTP_403_FORBIDDEN
        elif isinstance(exc, ClassroomNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, ClassroomConflictError):
            status_code = status.HTTP_409_CONFLICT
        else:
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(
            status_code=status_code,
            detail={"code": code, "message": str(exc), "retryable": False},
        ) from exc

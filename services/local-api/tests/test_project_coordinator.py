import sqlite3

import pytest

from zhangwen.artifacts.models import (
    ArtifactDependency,
    ArtifactKind,
    ArtifactStatus,
    DomainArtifactStatus,
)
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.coordinator import ProjectCoordinatorService
from zhangwen.projects.models import (
    DomainTaskStatus,
    ExpertType,
    HandoffStatus,
    PendingItemPriority,
    SharedFactStatus,
)
from zhangwen.projects.repository import ProjectRepository


def _project(tmp_path):
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project(
        name="Coordinator Test",
        initial_idea="Build a desk reminder",
        selected_expert_types=[
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        ],
    )
    # Coordinator tests build their own queue/task fixtures; Phase 4 project
    # creation seeds the first PendingItem and Task for real projects.
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute("DELETE FROM project_tasks WHERE project_id = ?", (workspace.project.id,))
        conn.execute(
            "DELETE FROM project_pending_items WHERE project_id = ?",
            (workspace.project.id,),
        )
    return repository, workspace.project.id


def test_shared_fact_lifecycle_prevents_direct_confirmed_overwrite(tmp_path) -> None:
    repository, project_id = _project(tmp_path)
    coordinator = ProjectCoordinatorService(repository.db_path)

    first = coordinator.propose_shared_fact(
        project_id=project_id,
        field="target_user",
        key="target_user",
        value="primary school students",
        source_type="expert",
        source_expert_type=ExpertType.PROBLEM_GUIDE,
        affects_artifact_ids=["artifact_solution"],
    )
    confirmed = coordinator.confirm_shared_fact(
        project_id=project_id,
        fact_id=first.id,
        confirmed_by="user",
    )
    assert confirmed.status == SharedFactStatus.CONFIRMED

    replacement = coordinator.propose_shared_fact(
        project_id=project_id,
        field="target_user",
        key="target_user",
        value="middle school students",
        source_type="expert",
        source_expert_type=ExpertType.SMART_ENGINEER,
    )
    facts = {fact.id: fact for fact in coordinator.list_shared_facts(project_id)}
    assert facts[first.id].status == SharedFactStatus.CONFIRMED
    assert facts[replacement.id].status == SharedFactStatus.PROPOSED

    confirmed_replacement = coordinator.confirm_shared_fact(
        project_id=project_id,
        fact_id=replacement.id,
        confirmed_by="user",
    )
    facts = {fact.id: fact for fact in coordinator.list_shared_facts(project_id)}
    assert confirmed_replacement.status == SharedFactStatus.CONFIRMED
    assert facts[first.id].status == SharedFactStatus.SUPERSEDED
    assert facts[first.id].supersededBy == replacement.id

    rejected = coordinator.propose_shared_fact(
        project_id=project_id,
        field="budget",
        value={"max": 200},
        source_type="expert",
        source_expert_type=ExpertType.PROBLEM_GUIDE,
    )
    assert coordinator.reject_shared_fact(
        project_id=project_id,
        fact_id=rejected.id,
    ).status == SharedFactStatus.REJECTED

    llm_candidate = coordinator.record_llm_candidate_fact(
        project_id=project_id,
        field="room",
        value="classroom",
        proposed_by=ExpertType.PROBLEM_GUIDE,
        reason="assistant summary",
    )
    assert llm_candidate.status == SharedFactStatus.PROPOSED


def test_pending_item_selection_is_unique_and_deterministic(tmp_path) -> None:
    repository, project_id = _project(tmp_path)
    coordinator = ProjectCoordinatorService(repository.db_path)

    normal = coordinator.create_pending_item(
        project_id=project_id,
        title="Normal",
        description="Normal queue item",
        priority=PendingItemPriority.NORMAL,
        reason="baseline",
        affected_experts=[ExpertType.PROBLEM_GUIDE],
        created_at="2026-07-10T00:00:00+00:00",
    )
    assert normal.isHighlighted is True

    coordinator.create_pending_item(
        project_id=project_id,
        title="Blocking one expert",
        description="Blocking queue item",
        priority=PendingItemPriority.BLOCKING,
        reason="blocked",
        affected_experts=[ExpertType.PROBLEM_GUIDE],
        created_at="2026-07-10T00:01:00+00:00",
    )
    two_experts = coordinator.create_pending_item(
        project_id=project_id,
        title="Blocking two experts",
        description="Blocking queue item",
        priority=PendingItemPriority.BLOCKING,
        reason="blocked",
        affected_experts=[ExpertType.PROBLEM_GUIDE, ExpertType.SMART_ENGINEER],
        created_at="2026-07-10T00:02:00+00:00",
    )
    assert two_experts.isHighlighted is True

    earlier = coordinator.create_pending_item(
        project_id=project_id,
        title="Earlier blocking",
        description="Earlier same priority and impact",
        priority=PendingItemPriority.BLOCKING,
        reason="blocked",
        affected_experts=[ExpertType.PROBLEM_GUIDE, ExpertType.SMART_ENGINEER],
        created_at="2026-07-10T00:00:30+00:00",
    )
    assert earlier.isHighlighted is True

    critical = coordinator.create_pending_item(
        project_id=project_id,
        title="Critical path tie",
        description="Critical path same timestamp",
        priority=PendingItemPriority.BLOCKING,
        reason="blocked",
        affected_experts=[ExpertType.PROBLEM_GUIDE, ExpertType.SMART_ENGINEER],
        critical_path=True,
        created_at="2026-07-10T00:00:30+00:00",
    )
    assert critical.isHighlighted is True

    safety = coordinator.create_pending_item(
        project_id=project_id,
        title="Safety",
        description="Safety queue item",
        priority=PendingItemPriority.SAFETY,
        reason="safety",
        affected_experts=[ExpertType.PROBLEM_GUIDE],
        created_at="2026-07-10T00:03:00+00:00",
    )
    assert safety.isHighlighted is True

    with sqlite3.connect(repository.db_path) as conn:
        highlighted_count = conn.execute(
            """
            SELECT COUNT(*) FROM project_pending_items
            WHERE project_id = ? AND status = 'open' AND is_highlighted = 1
            """,
            (project_id,),
        ).fetchone()[0]
    assert highlighted_count == 1

    coordinator.resolve_pending_item(project_id=project_id, pending_item_id=safety.id)
    highlighted = coordinator.refresh_highlighted_pending_item(project_id)
    assert highlighted is not None
    assert highlighted.id == critical.id


def test_handoff_and_task_state_machines(tmp_path) -> None:
    repository, project_id = _project(tmp_path)
    coordinator = ProjectCoordinatorService(repository.db_path)

    handoff = coordinator.create_handoff(
        project_id=project_id,
        from_expert=ExpertType.PROBLEM_GUIDE,
        to_expert=ExpertType.SMART_ENGINEER,
        handoff_type="implementation",
        summary="Need technical implementation",
        required_outputs=["bom", "io-map"],
    )
    assert handoff.status == HandoffStatus.PROPOSED
    with pytest.raises(ValueError):
        coordinator.transition_handoff(
            project_id=project_id,
            handoff_id=handoff.id,
            next_status=HandoffStatus.COMPLETED,
        )
    handoff = coordinator.transition_handoff(
        project_id=project_id,
        handoff_id=handoff.id,
        next_status=HandoffStatus.ACCEPTED,
    )
    handoff = coordinator.transition_handoff(
        project_id=project_id,
        handoff_id=handoff.id,
        next_status=HandoffStatus.IN_PROGRESS,
    )
    handoff = coordinator.transition_handoff(
        project_id=project_id,
        handoff_id=handoff.id,
        next_status=HandoffStatus.COMPLETED,
    )
    assert handoff.status == HandoffStatus.COMPLETED
    with pytest.raises(ValueError):
        coordinator.transition_handoff(
            project_id=project_id,
            handoff_id=handoff.id,
            next_status=HandoffStatus.ACCEPTED,
        )

    task = coordinator.create_task(
        project_id=project_id,
        title="Generate MicroPython",
        description="Generate code from confirmed IO map",
        owner_expert=ExpertType.SMART_ENGINEER,
    )
    assert task.status == DomainTaskStatus.QUEUED
    task = coordinator.transition_task(
        project_id=project_id,
        task_id=task.id,
        next_status=DomainTaskStatus.READY,
    )
    task = coordinator.transition_task(
        project_id=project_id,
        task_id=task.id,
        next_status=DomainTaskStatus.RUNNING,
    )
    task = coordinator.transition_task(
        project_id=project_id,
        task_id=task.id,
        next_status=DomainTaskStatus.COMPLETED,
    )
    assert task.status == DomainTaskStatus.COMPLETED
    with pytest.raises(ValueError):
        coordinator.transition_task(
            project_id=project_id,
            task_id=task.id,
            next_status=DomainTaskStatus.RUNNING,
        )


def test_artifact_dependency_index_and_outdated_propagation(tmp_path) -> None:
    repository, project_id = _project(tmp_path)
    artifacts = ArtifactRepository(repository.db_path)
    upstream_artifact_id = "artifact_spec_test"
    downstream_artifact_id = "artifact_code_test"

    upstream_v1 = artifacts.upsert_text_artifact(
        artifact_id=upstream_artifact_id,
        project_id=project_id,
        title="Project Spec",
        kind=ArtifactKind.DOCUMENT,
        status=ArtifactStatus.APPROVED,
        source_agent_id="spec-agent",
        source_entity_type="spec",
        source_entity_id="spec_v1",
        source_version=1,
        content="spec v1",
        summary="spec v1",
        mime_type="text/markdown",
        confirmed_at="2026-07-10T00:00:00+00:00",
    )
    downstream_v1 = artifacts.upsert_text_artifact(
        artifact_id=downstream_artifact_id,
        project_id=project_id,
        title="Code",
        kind=ArtifactKind.CODE,
        status=ArtifactStatus.APPROVED,
        source_agent_id="code-agent",
        source_entity_type="code",
        source_entity_id="code_v1",
        source_version=1,
        content="print('v1')",
        summary="code v1",
        mime_type="text/x-python",
        language="python",
        dependencies=[
            ArtifactDependency(
                artifactId=upstream_artifact_id,
                versionId=upstream_v1.id,
                version=1,
                kind="spec",
                label="Project Spec v1",
                status=ArtifactStatus.APPROVED.value,
            )
        ],
        confirmed_at="2026-07-10T00:01:00+00:00",
    )

    with sqlite3.connect(repository.db_path) as conn:
        conn.row_factory = sqlite3.Row
        dep_row = conn.execute(
            """
            SELECT * FROM artifact_dependencies
            WHERE artifact_version_id = ?
            """,
            (downstream_v1.id,),
        ).fetchone()
    assert dep_row is not None
    assert dep_row["upstream_artifact_id"] == upstream_artifact_id
    assert dep_row["upstream_version_id"] == upstream_v1.id
    assert dep_row["upstream_version"] == 1

    artifacts.upsert_text_artifact(
        artifact_id=upstream_artifact_id,
        project_id=project_id,
        title="Project Spec",
        kind=ArtifactKind.DOCUMENT,
        status=ArtifactStatus.APPROVED,
        source_agent_id="spec-agent",
        source_entity_type="spec",
        source_entity_id="spec_v2",
        source_version=2,
        content="spec v2",
        summary="spec v2",
        mime_type="text/markdown",
        confirmed_at="2026-07-10T00:02:00+00:00",
    )
    downstream = artifacts.get_artifact(project_id, downstream_artifact_id)
    affected_version = next(version for version in downstream.versions if version.id == downstream_v1.id)
    assert downstream.status == ArtifactStatus.STALE
    assert downstream.domainStatus == DomainArtifactStatus.OUTDATED
    assert affected_version.status == ArtifactStatus.STALE
    assert affected_version.domainStatus == DomainArtifactStatus.OUTDATED
    assert affected_version.staleReason == (
        f"上游产物 {upstream_artifact_id} 已确认新版本 v2。"
    )

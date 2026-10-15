"""Package Studio workflows: CAS, validation, replay, shadow, publish and rollback."""

from __future__ import annotations

import json
from pathlib import Path

from zhangwen.domains.packages.models import (
    CapabilityPackage,
    PackageConflictError,
    PackageDetailResponse,
    PackageInputSnapshot,
    PackageKind,
    PackageListResponse,
    PackagePublishResponse,
    PackageReplayResult,
    PackageRevision,
    PackageRunDiagnostics,
    PackageShadowRequest,
    PackageShadowResult,
    PackageValidationError,
    PackageWorkspace,
    PackageWorkspaceFileUpdate,
)
from zhangwen.domains.packages.plugin_host import PackagePluginHost
from zhangwen.domains.packages.repository import PackagePlatformRepository
from zhangwen.domains.packages.validation import (
    MAX_FILE_BYTES,
    MAX_PACKAGE_FILES,
    normalize_package_path,
)
from zhangwen.domains.packages.validator_host import PackageValidationHost


class PackagePlatformService:
    def __init__(
        self,
        data_dir: Path,
        *,
        owner_subject: str | None = None,
        plugin_host: PackagePluginHost | None = None,
        validation_host: PackageValidationHost | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._repository = PackagePlatformRepository(
            self._data_dir,
            owner_subject=owner_subject,
        )
        self._plugin_host = plugin_host or PackagePluginHost(self._data_dir)
        self._validation_host = validation_host or PackageValidationHost(self._data_dir)

    def list_packages(self, kind: PackageKind | None = None) -> PackageListResponse:
        return PackageListResponse(packages=self._repository.list_packages(kind))

    def detail(self, package_id: str) -> PackageDetailResponse:
        return self._repository.get_detail(package_id)

    def create_workspace(
        self,
        *,
        package_id: str | None,
        kind: PackageKind | None = None,
        slug: str | None = None,
        display_name: str | None = None,
    ) -> PackageWorkspace:
        return self._repository.create_workspace(
            package_id=package_id,
            kind=kind,
            slug=slug,
            display_name=display_name,
        )

    def workspace(self, workspace_id: str) -> PackageWorkspace:
        return self._repository.get_workspace(workspace_id)

    def save(
        self,
        workspace_id: str,
        *,
        expected_revision: int,
        files: list[PackageWorkspaceFileUpdate],
        event_reason: str = "API_SAVE",
    ) -> PackageWorkspace:
        workspace = self._repository.save_files(
            workspace_id,
            expected_revision=expected_revision,
            updates=[
                (file.path, file.content, file.expected_revision)
                for file in files
            ],
            event_reason=event_reason,
        )
        return self.validate(workspace.id)

    def validate(self, workspace_id: str) -> PackageWorkspace:
        workspace = self._repository.get_workspace(workspace_id)
        if workspace.draft_revision_id is None:
            raise PackageValidationError("请先保存草稿，再运行校验。")
        package = self._repository.get_package(workspace.package_id)
        files = {file.path: file.content for file in workspace.files}
        summary = self._validation_host.validate(package, files)
        return self._repository.record_validation(
            workspace.id,
            draft_revision_id=workspace.draft_revision_id,
            summary=summary,
        )

    def inputs(self, package_id: str) -> list[PackageInputSnapshot]:
        return self._repository.list_input_snapshots(package_id)

    def replay(self, workspace_id: str, turn_id: str) -> PackageReplayResult:
        workspace = self._repository.get_workspace(workspace_id)
        package = self._repository.get_package(workspace.package_id)
        stable = self._repository.stable_revision(package.id)
        snapshot = self._repository.get_input_snapshot(
            turn_id,
            package_id=package.id,
        )
        output, tool_plan, messages, duration_ms, output_bytes = self._evaluate(
            stable,
            snapshot,
        )
        diagnostics = PackageRunDiagnostics(
            messages=messages,
            durationMs=duration_ms,
            outputBytes=output_bytes,
            externalEffectsBlocked=True,
        )
        replay_id = self._repository.record_replay(
            workspace.id,
            revision_id=stable.id,
            input_snapshot=snapshot,
            output=output,
            tool_plan=tool_plan,
            diagnostics=diagnostics.model_dump(mode="json", by_alias=True),
        )
        return PackageReplayResult(
            id=replay_id,
            packageId=package.id,
            packageRevisionId=stable.id,
            inputSnapshot=snapshot,
            output=output,
            toolPlan=tool_plan,
            diagnostics=diagnostics,
            createdAt=_now(),
        )

    def shadow(self, workspace_id: str, turn_id: str) -> PackageShadowResult:
        workspace = self._repository.get_workspace(workspace_id)
        if workspace.draft_revision_id is None:
            raise PackageValidationError("影子运行需要已保存的草稿。")
        package = self._repository.get_package(workspace.package_id)
        baseline = self._repository.stable_revision(package.id)
        candidate = self._repository.get_revision(workspace.draft_revision_id)
        if candidate.validation_summary.status.value != "PASSED":
            raise PackageValidationError("影子运行前必须通过当前草稿校验。")
        snapshot = self._repository.get_input_snapshot(
            turn_id,
            package_id=package.id,
        )
        baseline_output, baseline_tools, baseline_messages, baseline_ms, baseline_bytes = self._evaluate(
            baseline,
            snapshot,
        )
        candidate_output, candidate_tools, candidate_messages, candidate_ms, candidate_bytes = self._evaluate(
            candidate,
            snapshot,
        )
        output_diff = _structured_diff(baseline_output, candidate_output)
        tool_diff = _structured_diff(
            {"toolPlan": baseline_tools},
            {"toolPlan": candidate_tools},
        )
        diagnostics = PackageRunDiagnostics(
            messages=[*baseline_messages, *candidate_messages],
            durationMs=baseline_ms + candidate_ms,
            outputBytes=baseline_bytes + candidate_bytes,
            externalEffectsBlocked=True,
        )
        shadow_id = self._repository.record_shadow(
            workspace.id,
            input_snapshot=snapshot,
            baseline_revision_id=baseline.id,
            candidate_revision_id=candidate.id,
            baseline_output=baseline_output,
            candidate_output=candidate_output,
            output_diff=output_diff,
            tool_plan_diff=tool_diff,
            diagnostics=diagnostics.model_dump(mode="json", by_alias=True),
            passed=True,
        )
        return PackageShadowResult(
            id=shadow_id,
            packageId=package.id,
            baselineRevisionId=baseline.id,
            candidateRevisionId=candidate.id,
            inputSnapshot=snapshot,
            baselineOutput=baseline_output,
            candidateOutput=candidate_output,
            outputDiff=output_diff,
            toolPlanDiff=tool_diff,
            diagnostics=diagnostics,
            status="PASSED",
            createdAt=_now(),
        )

    def publish(
        self,
        workspace_id: str,
        *,
        expected_revision: int,
        confirmed: bool,
    ) -> PackagePublishResponse:
        package, revision = self._repository.publish_workspace(
            workspace_id,
            expected_revision=expected_revision,
            confirmed=confirmed,
        )
        return PackagePublishResponse(package=package, revision=revision)

    def rollback(
        self,
        package_id: str,
        *,
        target_revision_id: str,
        expected_revision: int,
        confirmed: bool,
    ) -> PackagePublishResponse:
        package, revision = self._repository.rollback(
            package_id,
            target_revision_id=target_revision_id,
            expected_revision=expected_revision,
            confirmed=confirmed,
        )
        return PackagePublishResponse(package=package, revision=revision)

    def sync_external_workspace(self, workspace_id: str) -> PackageWorkspace:
        workspace = self._repository.get_workspace(workspace_id)
        root = self._repository.workspace_path(workspace_id)
        if not root.is_dir() or root.is_symlink():
            raise PackageConflictError("能力包工作区目录无效。")
        disk_files: dict[str, str] = {}
        for path in root.rglob("*"):
            if path.is_symlink():
                raise PackageConflictError("能力包工作区禁止符号链接。")
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            normalize_package_path(relative)
            if len(disk_files) >= MAX_PACKAGE_FILES:
                raise PackageConflictError("能力包工作区文件数量超过上限。")
            if path.stat().st_size > MAX_FILE_BYTES:
                raise PackageConflictError("能力包工作区文件超过大小上限。")
            disk_files[relative] = path.read_text(encoding="utf-8")
        current = {file.path: file for file in workspace.files}
        updates = [
            PackageWorkspaceFileUpdate(
                path=path,
                content=content,
                expectedRevision=current[path].revision if path in current else 0,
            )
            for path, content in disk_files.items()
            if path not in current or current[path].content != content
        ]
        if not updates:
            return workspace
        return self.save(
            workspace.id,
            expected_revision=workspace.revision,
            files=updates,
            event_reason="EXTERNAL_EDITOR",
        )

    def workspace_path(self, workspace_id: str) -> Path:
        return self._repository.workspace_path(workspace_id)

    def _evaluate(
        self,
        revision: PackageRevision,
        snapshot: PackageInputSnapshot,
    ) -> tuple[dict[str, object], list[dict[str, object]], list[str], int, int]:
        files = self._repository.get_revision_files(revision.id)
        try:
            manifest = json.loads(files["manifest.json"])
        except (KeyError, json.JSONDecodeError) as exc:
            raise PackageValidationError("能力包修订缺少有效 Manifest。") from exc
        if not isinstance(manifest, dict):
            raise PackageValidationError("能力包修订 Manifest 无效。")
        return self._plugin_host.evaluate(
            revision=revision,
            manifest=manifest,
            input_snapshot=snapshot.input,
        )


def _structured_diff(
    baseline: dict[str, object],
    candidate: dict[str, object],
) -> list[str]:
    left = json.dumps(baseline, ensure_ascii=False, sort_keys=True, indent=2).splitlines()
    right = json.dumps(candidate, ensure_ascii=False, sort_keys=True, indent=2).splitlines()
    if left == right:
        return []
    result: list[str] = []
    max_lines = max(len(left), len(right))
    for index in range(max_lines):
        before = left[index] if index < len(left) else ""
        after = right[index] if index < len(right) else ""
        if before != after:
            result.append(f"L{index + 1}: {before} → {after}"[:500])
        if len(result) >= 100:
            result.append("差异已截断。")
            break
    return result


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()

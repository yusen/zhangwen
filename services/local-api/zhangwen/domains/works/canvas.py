"""Versioned semantic canvas compiler layered on the existing Work facts.

The compiler is deterministic and local.  It can suggest capability-package
candidates, but it never executes a package, starts a service, or mutates a
device.  Canvas semantics and user layout are persisted separately in the
same project database used by every other Work domain.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zhangwen.auth.context import current_owner_subject
from zhangwen.creator.models import (
    ConversationProjectDraftV1,
    CreatorCommand,
    CreatorCommandRequest,
    CreatorWorkspace,
)
from zhangwen.creator.repository import CreatorRepository
from zhangwen.domains.events.store import RealtimeEventStore
from zhangwen.domains.inventory.repository import DevicePlatformRepository
from zhangwen.domains.packages.models import PackageKind
from zhangwen.domains.packages.repository import PackagePlatformRepository
from zhangwen.domains.works.canvas_llm import (
    CanvasLLMPlanCandidate,
    CanvasLLMPlanner,
    CanvasSceneCandidate,
)
from zhangwen.domains.works.models import (
    CanvasEdge,
    CanvasEdgeActiveState,
    CanvasGeneration,
    CanvasGenerationCommandRequest,
    CanvasGenerationSeed,
    CanvasGenerationStatus,
    CanvasGenerationStep,
    ConfirmCanvasProposalRequest,
    CanvasLayout,
    CanvasNode,
    CanvasNodeKind,
    CanvasNodePosition,
    CanvasSpec,
    CanvasTrustState,
    CanvasViewport,
    SaveCanvasLayoutRequest,
    StartCanvasGenerationRequest,
    WorkIntent,
    WorkIntentSource,
    WorkJourneyMilestone,
    WorkSceneActor,
    WorkSceneCamera,
    WorkSceneEnvironment,
    WorkSceneGeneration,
    WorkSceneKind,
    WorkSceneSpec,
    WorkSceneState,
    WorkSceneStateKind,
    WorkSceneSubject,
    WorkSceneTransition,
    WorkSceneVisualPart,
)
from zhangwen.llm.contracts import LLMErrorCode
from zhangwen.llm.development_fake import create_provider
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.projects.repository import ProjectRepository
from zhangwen.security.credentials import BackendCredentialStore
from zhangwen.settings.models import RuntimeModelSelection
from zhangwen.settings.provider_repository import ProviderSettingsConflictError


_LOCAL_OWNER = "__local__"
_LAYOUT_ALGORITHM = "semantic-lanes-v1"
_GENERATION_STEPS: tuple[CanvasGenerationStep, ...] = (
    CanvasGenerationStep.UNDERSTAND_INTENT,
    CanvasGenerationStep.EXTRACT_CAPABILITIES,
    CanvasGenerationStep.MATCH_PACKAGES,
    CanvasGenerationStep.VALIDATE_LOCALLY,
    CanvasGenerationStep.BUILD_CANVAS,
)
_STEP_PROGRESS: dict[CanvasGenerationStep, int] = {
    CanvasGenerationStep.UNDERSTAND_INTENT: 20,
    CanvasGenerationStep.EXTRACT_CAPABILITIES: 40,
    CanvasGenerationStep.MATCH_PACKAGES: 60,
    CanvasGenerationStep.VALIDATE_LOCALLY: 80,
    CanvasGenerationStep.BUILD_CANVAS: 100,
}
_STEP_STATUS: dict[CanvasGenerationStep, str] = {
    CanvasGenerationStep.UNDERSTAND_INTENT: "正在由当前作品模型形成完整流程",
    CanvasGenerationStep.EXTRACT_CAPABILITIES: "正在整理输入、行为和结果",
    CanvasGenerationStep.MATCH_PACKAGES: "正在匹配本机可用能力",
    CanvasGenerationStep.VALIDATE_LOCALLY: "正在执行本地完整性与安全检查",
    CanvasGenerationStep.BUILD_CANVAS: "正在把完整流程绘制成作品画面",
}


credential_store_factory = BackendCredentialStore
provider_factory = create_provider


class CanvasError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


class CanvasCompilationError(CanvasError):
    pass


class CanvasGenerationCanceled(CanvasError):
    def __init__(self) -> None:
        super().__init__(
            "CANVAS_GENERATION_CANCELED",
            "作品地图生成已取消。",
            status_code=409,
            retryable=False,
        )


@dataclass(frozen=True)
class _SemanticNodeDraft:
    key: str
    kind: CanvasNodeKind
    title: str
    summary: str
    capability: str
    trust_state: CanvasTrustState
    stage_affinity: WorkJourneyMilestone
    optional: bool
    match_terms: tuple[str, ...] = ()
    package_kinds: tuple[PackageKind, ...] = ()


@dataclass(frozen=True)
class _SemanticEdgeDraft:
    source_key: str
    target_key: str
    relation: str
    label: str


@dataclass(frozen=True)
class _PackageCandidate:
    id: str
    kind: PackageKind
    searchable: str


class CanvasCompiler:
    """Pure semantic rules plus read-only access to existing package facts."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)

    def understand_intent(
        self,
        workspace: CreatorWorkspace,
        seed: CanvasGenerationSeed,
        *,
        revision: int,
        created_at: str,
    ) -> WorkIntent:
        idea = _workspace_semantic_context(workspace)
        lowered = idea.casefold()
        inputs: list[str] = []
        behaviors: list[str] = []
        outputs: list[str] = []
        physical_actions: list[str] = []
        service_needs: list[str] = []
        structure_needs: list[str] = []
        environments: list[str] = []
        constraints: list[str] = []
        unknowns: list[str] = []

        if seed.environment_hint:
            environments.append(seed.environment_hint.strip())

        if _contains(lowered, "土壤", "湿度", "moisture", "soil"):
            _append_once(inputs, "土壤湿度")
        if _contains(lowered, "坐姿", "姿态", "posture", "倾斜", "角度"):
            _append_once(inputs, "姿态变化")
        if _contains(lowered, "温度", "temperature", "冷热"):
            _append_once(inputs, "环境温度")
        if _contains(lowered, "按钮", "触摸", "按下", "button", "touch"):
            _append_once(inputs, "用户操作")
        if _contains(lowered, "定时", "每天", "时间", "schedule", "timer"):
            _append_once(inputs, "时间条件")
        if not inputs:
            inputs.append("待确认的触发条件")
            unknowns.append("作品在什么情况下开始行动")

        if _contains(lowered, "坐姿", "posture", "姿态"):
            behaviors.append("识别持续的不良坐姿并避免频繁打扰")
        elif _contains(lowered, "浇花", "浇水", "水泵", "pump", "watering"):
            behaviors.append("根据条件安全控制浇水并在异常时停止")
        elif _contains(lowered, "灯", "light", "led", "照明"):
            behaviors.append("根据输入调整灯光或提醒状态")
        else:
            behaviors.append("根据输入决定下一步动作")

        if _contains(lowered, "手机", "通知", "消息", "phone", "notify"):
            outputs.append("向手机发送提醒")
            service_needs.append("本地消息服务")
        if _contains(lowered, "灯", "亮", "颜色", "light", "led"):
            outputs.append("给出可见的灯光结果")
        if _contains(lowered, "声音", "蜂鸣", "语音", "sound", "audio"):
            outputs.append("发出可听见的提醒")
        if _contains(lowered, "浇花", "浇水", "水泵", "pump", "watering"):
            outputs.append("安全控制水泵启停")
            physical_actions.append("驱动水泵")
        if _contains(lowered, "电机", "马达", "motor", "servo", "舵机"):
            outputs.append("控制机械运动")
            physical_actions.append("驱动电机或舵机")
        if not outputs:
            outputs.append("产生用户可以观察的结果")

        if _contains(lowered, "mqtt", "远程", "联网", "网络", "remote"):
            _append_once(service_needs, "受控的本地通信服务")
        if seed.network_preference == "LOCAL_ONLY":
            _append_once(service_needs, "仅本机通信")
        elif seed.network_preference == "HOME_LAN":
            _append_once(service_needs, "家庭网络内的本地通信")
            constraints.append("开放家庭网络前必须由用户确认")
        elif seed.network_preference == "EXTERNAL_EXISTING":
            _append_once(service_needs, "连接用户已有的外部服务")
            constraints.append("外部服务地址和凭据必须通过本地安全设置")
        else:
            constraints.append("默认离线优先，不自动开放网络")

        if _contains(
            lowered,
            "外壳",
            "支架",
            "防水",
            "穿戴",
            "固定",
            "开孔",
            "3d打印",
            "3d 打印",
            "enclosure",
            "mount",
            "wearable",
        ):
            structure_needs.append("与作品用途匹配的结构和装配")

        if not environments and _contains(lowered, "户外", "室外", "outdoor"):
            environments.append("户外")
        elif not environments and _contains(lowered, "桌面", "花盆", "家庭", "室内", "desktop", "home"):
            environments.append("室内")

        if physical_actions:
            constraints.append("执行器必须有独立供电、保护和异常关闭策略")
        if seed.selected_inventory_item_ids:
            constraints.append("优先评估用户已选择的设备，不自动确认兼容")
        if seed.reference_names:
            constraints.append(f"已提供 {len(seed.reference_names)} 个参考附件供本地整理")
        if not seed.selected_inventory_item_ids:
            unknowns.append("具体实现载体仍需与本机能力包匹配")

        critical_question = None
        if unknowns:
            critical_question = {
                "作品在什么情况下开始行动": "你希望作品在什么情况下开始行动？",
                "具体实现载体仍需与本机能力包匹配": "你手边是否已有希望优先使用的设备？",
            }.get(unknowns[0], f"请确认：{unknowns[0]}？")
        explicit_groups = sum(
            bool(group)
            for group in (
                environments,
                inputs if inputs != ["待确认的触发条件"] else [],
                outputs,
                physical_actions,
                service_needs,
                structure_needs,
            )
        )
        confidence = min(0.95, 0.45 + explicit_groups * 0.08)
        digest = _digest(
            {
                "workId": workspace.work_id,
                "idea": idea,
                "seed": seed.model_dump(by_alias=True, mode="json"),
                "revision": revision,
            }
        )
        return WorkIntent(
            id=f"intent_{digest[:24]}",
            workId=workspace.work_id,
            revision=revision,
            title=workspace.name,
            summary=idea,
            users=["作品使用者"],
            environments=environments,
            inputs=inputs,
            behaviors=behaviors,
            outputs=outputs,
            physicalActions=physical_actions,
            serviceNeeds=service_needs,
            structureNeeds=structure_needs,
            constraints=constraints,
            unknowns=unknowns,
            criticalQuestion=critical_question,
            confidence=round(confidence, 2),
            source=seed.source,
            createdAt=created_at,
        )

    def intent_from_candidate(
        self,
        workspace: CreatorWorkspace,
        seed: CanvasGenerationSeed,
        candidate: CanvasLLMPlanCandidate,
        *,
        revision: int,
        created_at: str,
    ) -> WorkIntent:
        """Turn validated model semantics into a server-owned immutable intent."""

        constraints = list(candidate.constraints)
        if candidate.physical_actions:
            _append_once(
                constraints,
                "真实执行器必须经过独立供电、保护、确认、回读和异常停止检查",
            )
        if candidate.service_needs:
            _append_once(
                constraints,
                "联网和服务凭据只由本地安全边界管理，启动前需要相应确认",
            )
        if seed.network_preference == "LOCAL_ONLY":
            _append_once(constraints, "通信仅限本机")
        elif seed.network_preference == "HOME_LAN":
            _append_once(constraints, "开放家庭网络前必须由用户确认")
        elif seed.network_preference == "EXTERNAL_EXISTING":
            _append_once(constraints, "外部服务地址和凭据必须通过本地安全设置")
        else:
            _append_once(constraints, "默认离线优先，不自动开放网络")
        if seed.selected_inventory_item_ids:
            _append_once(constraints, "优先评估已选设备，但不自动确认兼容")
        if seed.reference_names:
            _append_once(
                constraints,
                f"已提供 {len(seed.reference_names)} 个参考附件供本地校验",
            )

        unknowns = list(candidate.unknowns)
        if not seed.selected_inventory_item_ids:
            _append_once(unknowns, "具体实现载体仍需与本机能力包匹配")
        payload = candidate.model_dump(by_alias=True, mode="json")
        digest = _digest(
            {
                "workId": workspace.work_id,
                "candidate": payload,
                "source": seed.source.value,
                "revision": revision,
            }
        )
        return WorkIntent(
            id=f"intent_{digest[:24]}",
            workId=workspace.work_id,
            revision=revision,
            title=workspace.name,
            summary=candidate.project_summary,
            users=_bounded_unique(candidate.users, 8),
            environments=_bounded_unique(candidate.environments, 8),
            inputs=_bounded_unique(candidate.inputs, 12),
            behaviors=_bounded_unique(candidate.behaviors, 8),
            outputs=_bounded_unique(candidate.outputs, 12),
            physicalActions=_bounded_unique(candidate.physical_actions, 8),
            serviceNeeds=_bounded_unique(candidate.service_needs, 8),
            structureNeeds=_bounded_unique(candidate.structure_needs, 8),
            constraints=_bounded_unique(constraints, 16),
            unknowns=_bounded_unique(unknowns, 12),
            criticalQuestion=candidate.critical_question,
            confidence=candidate.confidence,
            source=seed.source,
            createdAt=created_at,
        )

    def extract_capabilities(
        self,
        intent: WorkIntent,
    ) -> tuple[list[_SemanticNodeDraft], list[_SemanticEdgeDraft]]:
        lowered = intent.summary.casefold()
        nodes: list[_SemanticNodeDraft] = [
            _SemanticNodeDraft(
                key="work",
                kind=CanvasNodeKind.WORK,
                title=intent.title,
                summary=intent.summary[:1000],
                capability="work.intent",
                trust_state=CanvasTrustState.CONFIRMED,
                stage_affinity=WorkJourneyMilestone.CLARIFY,
                optional=False,
            )
        ]
        edges: list[_SemanticEdgeDraft] = []

        input_specs: list[tuple[str, str, tuple[str, ...]]] = []
        handled_inputs: set[str] = set()
        if "土壤湿度" in intent.inputs:
            input_specs.append(("soil-moisture", "土壤湿度", ("soil", "moisture", "土壤", "湿度")))
            handled_inputs.add("土壤湿度")
        if "姿态变化" in intent.inputs:
            input_specs.append(("posture", "姿态变化", ("imu", "accelerometer", "姿态", "加速度")))
            handled_inputs.add("姿态变化")
        if "环境温度" in intent.inputs:
            input_specs.append(("temperature", "环境温度", ("temperature", "温度")))
            handled_inputs.add("环境温度")
        if "用户操作" in intent.inputs:
            input_specs.append(("user-action", "用户操作", ("button", "touch", "按钮", "触摸")))
            handled_inputs.add("用户操作")
        if "时间条件" in intent.inputs:
            input_specs.append(("schedule", "时间条件", ("timer", "clock", "rtc", "时间")))
            handled_inputs.add("时间条件")
        for index, input_value in enumerate(intent.inputs):
            if input_value in handled_inputs:
                continue
            input_specs.append((f"candidate-{index + 1}", input_value, (input_value,)))
        if not input_specs:
            input_specs.append(("trigger", "待确认的触发条件", ()))
        for key, title, terms in input_specs:
            nodes.append(
                _SemanticNodeDraft(
                    key=f"input:{key}",
                    kind=CanvasNodeKind.INPUT,
                    title=title,
                    summary="作品需要读取或接收这一输入。",
                    capability=f"input.{key}",
                    trust_state=(
                        CanvasTrustState.NEEDS_CONFIRMATION
                        if key == "trigger"
                        else CanvasTrustState.CONFIRMED
                    ),
                    stage_affinity=WorkJourneyMilestone.TRY,
                    optional=False,
                    match_terms=terms,
                    package_kinds=(PackageKind.DEVICE_PACKAGE,),
                )
            )

        behavior_key = "decision"
        if _contains(lowered, "坐姿", "posture", "姿态"):
            behavior_key = "posture-rule"
        elif _contains(lowered, "浇水", "水泵", "pump"):
            behavior_key = "watering-rule"
        elif _contains(lowered, "灯", "light", "led"):
            behavior_key = "lighting-rule"
        nodes.append(
            _SemanticNodeDraft(
                key=f"behavior:{behavior_key}",
                kind=CanvasNodeKind.BEHAVIOR,
                title="作品判断与行为",
                summary=intent.behaviors[0],
                capability=f"behavior.{behavior_key}",
                trust_state=CanvasTrustState.CONFIRMED,
                stage_affinity=WorkJourneyMilestone.TRY,
                optional=False,
                package_kinds=(PackageKind.RUNTIME_PACKAGE,),
            )
        )
        for input_key, _, _ in input_specs:
            edges.append(
                _SemanticEdgeDraft(
                    source_key=f"input:{input_key}",
                    target_key=f"behavior:{behavior_key}",
                    relation="INFORMS",
                    label="提供输入",
                )
            )

        output_keys: list[str] = []
        for index, output in enumerate(intent.outputs):
            if "手机" in output:
                key = "phone-notification"
                terms = ("notification", "message", "mqtt", "通知", "消息")
            elif "灯光" in output:
                key = "visible-light"
                terms = ("rgb", "led", "light", "灯")
            elif "听见" in output:
                key = "sound"
                terms = ("audio", "buzzer", "speaker", "声音", "蜂鸣")
            elif "水泵" in output:
                key = "pump-state"
                terms = ("pump", "water", "水泵")
            elif "机械" in output:
                key = "motion"
                terms = ("motor", "servo", "电机", "舵机")
            else:
                key = f"visible-result-{index + 1}"
                terms = ()
            output_keys.append(f"output:{key}")
            nodes.append(
                _SemanticNodeDraft(
                    key=f"output:{key}",
                    kind=CanvasNodeKind.OUTPUT,
                    title=output,
                    summary="这是用户可以观察和验收的作品结果。",
                    capability=f"output.{key}",
                    trust_state=CanvasTrustState.CONFIRMED,
                    stage_affinity=WorkJourneyMilestone.TRY,
                    optional=False,
                    match_terms=terms,
                    package_kinds=(PackageKind.DEVICE_PACKAGE,),
                )
            )
            edges.append(
                _SemanticEdgeDraft(
                    source_key=f"behavior:{behavior_key}",
                    target_key=f"output:{key}",
                    relation="PRODUCES",
                    label="产生结果",
                )
            )

        for index, action in enumerate(intent.physical_actions):
            key = "pump" if "水泵" in action else "motor"
            if index:
                key = f"{key}-{index + 1}"
            terms = ("pump", "water", "水泵") if "水泵" in action else ("motor", "servo", "电机", "舵机")
            nodes.append(
                _SemanticNodeDraft(
                    key=f"physical-action:{key}",
                    kind=CanvasNodeKind.PHYSICAL_ACTION,
                    title=action,
                    summary="真实执行前必须完成供电、保护、确认和回读。",
                    capability=f"physical-action.{key}",
                    trust_state=CanvasTrustState.NEEDS_CONFIRMATION,
                    stage_affinity=WorkJourneyMilestone.MAKE,
                    optional=False,
                    match_terms=terms,
                    package_kinds=(PackageKind.DEVICE_PACKAGE,),
                )
            )
            edges.append(
                _SemanticEdgeDraft(
                    source_key=f"behavior:{behavior_key}",
                    target_key=f"physical-action:{key}",
                    relation="CONTROLS",
                    label="受控执行",
                )
            )

        service_keys: list[str] = []
        for index, need in enumerate(intent.service_needs):
            key = "local-messaging" if _contains(need.casefold(), "消息", "通信", "本机", "网络") else f"service-{index + 1}"
            if f"service:{key}" in service_keys:
                continue
            service_keys.append(f"service:{key}")
            nodes.append(
                _SemanticNodeDraft(
                    key=f"service:{key}",
                    kind=CanvasNodeKind.SERVICE,
                    title=need,
                    summary="这里只形成服务候选，不会自动启动网络或开放监听。",
                    capability=f"service.{key}",
                    trust_state=CanvasTrustState.CANDIDATE,
                    stage_affinity=WorkJourneyMilestone.MAKE,
                    optional=True,
                    match_terms=("mqtt", "message", "local", "通信", "消息"),
                    package_kinds=(PackageKind.SERVICE_PACKAGE,),
                )
            )
            edges.append(
                _SemanticEdgeDraft(
                    source_key=f"behavior:{behavior_key}",
                    target_key=f"service:{key}",
                    relation="USES_SERVICE",
                    label="需要通信",
                )
            )

        if intent.structure_needs:
            nodes.append(
                _SemanticNodeDraft(
                    key="structure:assembly",
                    kind=CanvasNodeKind.STRUCTURE,
                    title="结构与装配",
                    summary=intent.structure_needs[0],
                    capability="structure.assembly",
                    trust_state=CanvasTrustState.CANDIDATE,
                    stage_affinity=WorkJourneyMilestone.MAKE,
                    optional=True,
                )
            )

        needs_power = bool(intent.physical_actions)
        if needs_power:
            nodes.append(
                _SemanticNodeDraft(
                    key="power:protected-supply",
                    kind=CanvasNodeKind.POWER,
                    title="供电与保护",
                    summary="执行器需要独立供电、保护和异常关闭策略。",
                    capability="power.protected-supply",
                    trust_state=CanvasTrustState.NEEDS_CONFIRMATION,
                    stage_affinity=WorkJourneyMilestone.MAKE,
                    optional=False,
                    match_terms=("power", "supply", "电源", "供电"),
                    package_kinds=(PackageKind.DEVICE_PACKAGE,),
                )
            )

        device_terms: tuple[str, ...] = tuple(
            term
            for node in nodes
            if node.kind in {CanvasNodeKind.INPUT, CanvasNodeKind.OUTPUT, CanvasNodeKind.PHYSICAL_ACTION}
            for term in node.match_terms
        )
        nodes.append(
            _SemanticNodeDraft(
                key="device:implementation-carrier",
                kind=CanvasNodeKind.DEVICE,
                title="实现载体待选择",
                summary="只展示本机能够证明的候选；找不到时不会虚构板型。",
                capability="device.implementation-carrier",
                trust_state=CanvasTrustState.NEEDS_CONFIRMATION,
                stage_affinity=WorkJourneyMilestone.MAKE,
                optional=False,
                match_terms=device_terms,
                package_kinds=(PackageKind.DEVICE_PACKAGE,),
            )
        )
        edges.append(
            _SemanticEdgeDraft(
                source_key="device:implementation-carrier",
                target_key=f"behavior:{behavior_key}",
                relation="HOSTS",
                label="承载逻辑",
            )
        )
        if intent.structure_needs:
            edges.append(
                _SemanticEdgeDraft(
                    source_key="structure:assembly",
                    target_key="device:implementation-carrier",
                    relation="MOUNTS",
                    label="固定与装配",
                )
            )
        if needs_power:
            for node in nodes:
                if node.kind in {CanvasNodeKind.DEVICE, CanvasNodeKind.PHYSICAL_ACTION}:
                    edges.append(
                        _SemanticEdgeDraft(
                            source_key="power:protected-supply",
                            target_key=node.key,
                            relation="POWERS",
                            label="安全供电",
                        )
                    )
        for output_key in output_keys:
            edges.append(
                _SemanticEdgeDraft(
                    source_key="work",
                    target_key=output_key,
                    relation="ACCEPTS",
                    label="用于验收",
                )
            )
        return nodes, edges

    def package_catalog(self) -> list[_PackageCandidate]:
        repository = PackagePlatformRepository(self._data_dir)
        candidates: list[_PackageCandidate] = []
        for package in repository.list_packages():
            if package.stable_revision_id is None:
                continue
            searchable_parts = [package.id, package.slug, package.display_name]
            try:
                files = repository.get_revision_files(package.stable_revision_id)
            except Exception:
                files = {}
            manifest = files.get("manifest.json", "")
            searchable_parts.append(manifest[:16_000])
            candidates.append(
                _PackageCandidate(
                    id=package.id,
                    kind=package.kind,
                    searchable=" ".join(searchable_parts).casefold(),
                )
            )
        return candidates

    def selected_device_package_ids(
        self,
        selected_inventory_item_ids: list[str],
    ) -> list[str]:
        if not selected_inventory_item_ids:
            return []
        inventory = DevicePlatformRepository(self._data_dir).list_inventory()
        by_id = {item.id: item for item in inventory}
        missing = [item_id for item_id in selected_inventory_item_ids if item_id not in by_id]
        if missing:
            raise CanvasCompilationError(
                "CANVAS_INVENTORY_ITEM_NOT_FOUND",
                "所选设备已不存在或不属于当前账户，请重新选择。",
                status_code=404,
                retryable=False,
            )
        return _unique(by_id[item_id].device_package_id for item_id in selected_inventory_item_ids)

    def match_packages(
        self,
        work_id: str,
        drafts: list[_SemanticNodeDraft],
        edge_drafts: list[_SemanticEdgeDraft],
        catalog: list[_PackageCandidate],
        selected_device_package_ids: list[str],
    ) -> tuple[list[CanvasNode], list[CanvasEdge]]:
        nodes: list[CanvasNode] = []
        for draft in drafts:
            package_ids: list[str] = []
            if draft.kind is CanvasNodeKind.DEVICE:
                package_ids.extend(selected_device_package_ids)
            for candidate in catalog:
                if draft.package_kinds and candidate.kind not in draft.package_kinds:
                    continue
                if not draft.match_terms:
                    if candidate.kind is PackageKind.RUNTIME_PACKAGE and draft.kind is CanvasNodeKind.BEHAVIOR:
                        package_ids.append(candidate.id)
                    continue
                if any(term.casefold() in candidate.searchable for term in draft.match_terms):
                    package_ids.append(candidate.id)
            package_ids = _unique(package_ids)[:12]
            trust_state = draft.trust_state
            if draft.kind is CanvasNodeKind.DEVICE:
                trust_state = (
                    CanvasTrustState.CANDIDATE
                    if package_ids
                    else CanvasTrustState.NEEDS_CONFIRMATION
                )
            nodes.append(
                CanvasNode(
                    id=_node_id(work_id, draft.key),
                    kind=draft.kind,
                    title=draft.title,
                    summary=draft.summary,
                    capability=draft.capability,
                    trustState=trust_state,
                    packageCandidateIds=package_ids,
                    evidenceRefs=[],
                    stageAffinity=draft.stage_affinity,
                    optional=draft.optional,
                )
            )
        node_by_key = {
            draft.key: node for draft, node in zip(drafts, nodes, strict=True)
        }
        edges: list[CanvasEdge] = []
        for edge in edge_drafts:
            source = node_by_key.get(edge.source_key)
            target = node_by_key.get(edge.target_key)
            if source is None or target is None:
                raise CanvasCompilationError(
                    "CANVAS_EDGE_NODE_MISSING",
                    "作品地图内部连接不完整，请重试。",
                    retryable=True,
                )
            states = {source.trust_state, target.trust_state}
            if CanvasTrustState.UNSUPPORTED in states:
                active_state = CanvasEdgeActiveState.BLOCKED
            elif states & {
                CanvasTrustState.CANDIDATE,
                CanvasTrustState.DEFAULTED,
                CanvasTrustState.NEEDS_CONFIRMATION,
            }:
                active_state = CanvasEdgeActiveState.PROPOSED
            else:
                active_state = CanvasEdgeActiveState.ACTIVE
            edges.append(
                CanvasEdge(
                    id=_edge_id(work_id, edge.relation, source.id, target.id),
                    sourceNodeId=source.id,
                    targetNodeId=target.id,
                    relation=edge.relation,
                    label=edge.label,
                    activeState=active_state,
                )
            )
        return nodes, edges

    def validate(self, nodes: list[CanvasNode], edges: list[CanvasEdge]) -> None:
        node_ids = [node.id for node in nodes]
        if len(node_ids) != len(set(node_ids)):
            raise CanvasCompilationError(
                "CANVAS_NODE_ID_CONFLICT",
                "作品地图节点标识冲突，请重试。",
                retryable=True,
            )
        known = set(node_ids)
        if any(edge.source_node_id not in known or edge.target_node_id not in known for edge in edges):
            raise CanvasCompilationError(
                "CANVAS_EDGE_NODE_MISSING",
                "作品地图内部连接不完整，请重试。",
                retryable=True,
            )
        has_physical_action = any(node.kind is CanvasNodeKind.PHYSICAL_ACTION for node in nodes)
        has_power = any(node.kind is CanvasNodeKind.POWER for node in nodes)
        if has_physical_action and not has_power:
            raise CanvasCompilationError(
                "CANVAS_POWER_SAFETY_MISSING",
                "包含执行器的作品必须先形成供电与保护候选。",
                retryable=False,
            )

    def build_spec(
        self,
        workspace: CreatorWorkspace,
        intent: WorkIntent,
        nodes: list[CanvasNode],
        edges: list[CanvasEdge],
        *,
        revision: int,
        created_at: str,
        scene_candidate: CanvasSceneCandidate | None = None,
        runtime_selection: RuntimeModelSelection | None = None,
    ) -> CanvasSpec:
        scene_generation = _scene_generation(runtime_selection)
        semantic_payload = {
            "workId": workspace.work_id,
            "revision": revision,
            "intent": intent.model_dump(by_alias=True, mode="json"),
            "nodes": [node.model_dump(by_alias=True, mode="json") for node in nodes],
            "edges": [edge.model_dump(by_alias=True, mode="json") for edge in edges],
            "sceneCandidate": (
                scene_candidate.model_dump(by_alias=True, mode="json")
                if scene_candidate is not None
                else None
            ),
            "sceneGeneration": scene_generation.model_dump(
                by_alias=True,
                mode="json",
            ),
        }
        digest = _digest(
            semantic_payload
        )
        canvas_id = f"canvas_{digest[:24]}"
        pending = sum(
            node.trust_state
            in {CanvasTrustState.CANDIDATE, CanvasTrustState.NEEDS_CONFIRMATION}
            for node in nodes
        )
        status = (
            f"作品地图已形成，有 {pending} 项需要继续确认。"
            if pending
            else "作品地图已形成，当前语义结构完整。"
        )
        return CanvasSpec(
            id=canvas_id,
            workId=workspace.work_id,
            revision=revision,
            workIntent=intent,
            nodes=nodes,
            edges=edges,
            scene=self.build_scene(
                intent,
                nodes,
                edges,
                canvas_id=canvas_id,
                canvas_revision=revision,
                candidate=scene_candidate,
                generation=scene_generation,
            ),
            naturalStatus=status,
            createdAt=created_at,
        )

    def build_scene(
        self,
        intent: WorkIntent,
        nodes: list[CanvasNode],
        edges: list[CanvasEdge],
        *,
        canvas_id: str,
        canvas_revision: int,
        candidate: CanvasSceneCandidate | None = None,
        generation: WorkSceneGeneration | None = None,
    ) -> WorkSceneSpec:
        """Compile a bounded visual projection from the semantic canvas facts."""

        lowered = f"{intent.title}\n{intent.summary}".casefold()
        local_scene_kind, local_subject_kind, local_subject_label = _scene_identity(
            lowered,
            intent,
        )
        if candidate is None:
            scene_kind, subject_kind, subject_label = (
                local_scene_kind,
                local_subject_kind,
                local_subject_label,
            )
            environment = _scene_environment(intent)
        else:
            scene_kind = WorkSceneKind(candidate.kind)
            subject_kind = candidate.subject.kind
            subject_label = candidate.subject.label
            # The model supplies presentation semantics, but it must not replace an
            # explicit project fact such as "pure software/web app" with a physical
            # product category merely because the subject matter mentions reminders.
            if local_subject_kind == "SOFTWARE":
                scene_kind = local_scene_kind
                subject_kind = local_subject_kind
                subject_label = local_subject_label
            environment = WorkSceneEnvironment.model_validate(
                candidate.environment.model_dump(mode="json")
            )
        role_by_kind: dict[CanvasNodeKind, str] = {
            CanvasNodeKind.WORK: "SUBJECT",
            CanvasNodeKind.INPUT: "INPUT",
            CanvasNodeKind.BEHAVIOR: "DECISION",
            CanvasNodeKind.OUTPUT: "RESULT",
            CanvasNodeKind.PHYSICAL_ACTION: "ACTION",
            CanvasNodeKind.POWER: "POWER",
            CanvasNodeKind.STRUCTURE: "STRUCTURE",
            CanvasNodeKind.SERVICE: "SERVICE",
            CanvasNodeKind.DEVICE: "SUBJECT",
        }
        grouped: dict[str, list[CanvasNode]] = {}
        for node in nodes:
            grouped.setdefault(role_by_kind[node.kind], []).append(node)
        ordered_roles = (
            "SUBJECT",
            "INPUT",
            "DECISION",
            "ACTION",
            "RESULT",
            "POWER",
            "STRUCTURE",
            "SERVICE",
        )
        candidate_parts = {
            item.role: item
            for item in (candidate.visual_parts if candidate is not None else [])
        }
        visual_parts = [
            WorkSceneVisualPart(
                id=f"scene-part-{role.casefold()}",
                role=role,
                label=(
                    candidate_parts[role].label
                    if role in candidate_parts
                    else _scene_part_label(role, role_nodes)
                ),
                description=(
                    candidate_parts[role].description
                    if role in candidate_parts
                    else "；".join(node.summary for node in role_nodes)[:500]
                ),
                nodeIds=[node.id for node in role_nodes],
                optional=all(node.optional for node in role_nodes),
            )
            for role in ordered_roles
            if (role_nodes := grouped.get(role))
        ]
        part_by_role = {part.role: part.id for part in visual_parts}
        state_roles: dict[WorkSceneStateKind, tuple[str, ...]] = {
            WorkSceneStateKind.IDLE: ("SUBJECT",),
            WorkSceneStateKind.TRIGGERED: ("SUBJECT", "INPUT"),
            WorkSceneStateKind.DECIDING: ("SUBJECT", "INPUT", "DECISION"),
            WorkSceneStateKind.ACTING: ("SUBJECT", "DECISION", "ACTION", "POWER"),
            WorkSceneStateKind.RESULT: ("SUBJECT", "RESULT", "SERVICE"),
            WorkSceneStateKind.FAULT: ("SUBJECT", "INPUT", "ACTION", "POWER"),
        }
        if candidate is None:
            narratives: dict[WorkSceneStateKind, str] = {
                WorkSceneStateKind.IDLE: f"{subject_label}在{environment.label}等待触发。",
                WorkSceneStateKind.TRIGGERED: f"作品观察到{_joined(intent.inputs, '待确认的触发')}。",
                WorkSceneStateKind.DECIDING: _joined(intent.behaviors, "作品正在判断下一步动作。"),
                WorkSceneStateKind.ACTING: _joined(
                    intent.physical_actions or intent.outputs,
                    "作品正在执行当前动作。",
                ),
                WorkSceneStateKind.RESULT: f"使用者可以观察到{_joined(intent.outputs, '作品结果')}。",
                WorkSceneStateKind.FAULT: "发生异常时作品停止危险动作，并等待用户检查。",
            }
        else:
            narratives = {
                WorkSceneStateKind.IDLE: candidate.state_narratives.idle,
                WorkSceneStateKind.TRIGGERED: candidate.state_narratives.triggered,
                WorkSceneStateKind.DECIDING: candidate.state_narratives.deciding,
                WorkSceneStateKind.ACTING: candidate.state_narratives.acting,
                WorkSceneStateKind.RESULT: candidate.state_narratives.result,
                WorkSceneStateKind.FAULT: candidate.state_narratives.fault,
            }
        states = [
            WorkSceneState(
                id=f"scene-state-{kind.value.casefold()}",
                kind=kind,
                label={
                    WorkSceneStateKind.IDLE: "等待中",
                    WorkSceneStateKind.TRIGGERED: "发现变化",
                    WorkSceneStateKind.DECIDING: "正在判断",
                    WorkSceneStateKind.ACTING: "正在行动",
                    WorkSceneStateKind.RESULT: "结果出现",
                    WorkSceneStateKind.FAULT: "安全停止",
                }[kind],
                narrative=narratives[kind],
                activePartIds=[
                    part_by_role[role]
                    for role in state_roles[kind]
                    if role in part_by_role
                ],
            )
            for kind in WorkSceneStateKind
        ]
        state_ids = {state.kind: state.id for state in states}
        relation_groups = _scene_relation_groups(nodes, edges)
        flow = candidate.flow if candidate is not None else None
        transition_steps = (
            (WorkSceneStateKind.IDLE, WorkSceneStateKind.TRIGGERED, flow.trigger if flow else "作品发现触发", "TRIGGER"),
            (WorkSceneStateKind.TRIGGERED, WorkSceneStateKind.DECIDING, flow.decide if flow else "作品开始判断", "DECIDE"),
            (WorkSceneStateKind.DECIDING, WorkSceneStateKind.ACTING, flow.act if flow else "作品执行动作", "ACT"),
            (WorkSceneStateKind.ACTING, WorkSceneStateKind.RESULT, flow.result if flow else "结果变得可见", "RESULT"),
            (WorkSceneStateKind.ACTING, WorkSceneStateKind.FAULT, flow.fault if flow else "异常时安全停止", "FAULT"),
        )
        transitions = [
            WorkSceneTransition(
                id=f"scene-transition-{source.value.casefold()}-{target.value.casefold()}",
                fromStateId=state_ids[source],
                toStateId=state_ids[target],
                label=label,
                edgeIds=relation_groups[group] or [edges[0].id],
            )
            for source, target, label, group in transition_steps
            if edges
        ]
        if candidate is None:
            actors = [
                WorkSceneActor(
                    id="scene-actor-user",
                    kind="PERSON",
                    label=intent.users[0] if intent.users else "作品使用者",
                    role="触发作品并观察结果",
                )
            ]
            if scene_kind is WorkSceneKind.PLANT:
                actors.append(
                    WorkSceneActor(
                        id="scene-actor-plant",
                        kind="PLANT",
                        label="植物",
                        role="作品照料的对象",
                    )
                )
        else:
            actors = [
                WorkSceneActor(
                    id=f"scene-actor-{index + 1}",
                    kind=actor.kind,
                    label=actor.label,
                    role=actor.role,
                )
                for index, actor in enumerate(candidate.actors)
            ]
        subject_part_id = part_by_role.get("SUBJECT", visual_parts[0].id)
        behavior = _joined(intent.behaviors, "根据输入决定动作")
        result = _joined(intent.outputs, "产生可观察结果")
        return WorkSceneSpec(
            schemaVersion=1,
            kind=scene_kind,
            title=candidate.title if candidate is not None else intent.title,
            description=(
                candidate.description
                if candidate is not None
                else f"在{environment.label}中，{subject_label}会{behavior}，并让使用者看到{result}。"
            ),
            environment=environment,
            subject=WorkSceneSubject(
                kind=subject_kind,
                label=subject_label,
                description=(
                    candidate.subject.description
                    if candidate is not None
                    else intent.summary[:500]
                ),
            ),
            actors=actors,
            visualParts=visual_parts,
            states=states,
            transitions=transitions,
            camera=WorkSceneCamera(
                composition=(
                    candidate.composition
                    if candidate is not None
                    else "WIDE_CONTEXT"
                    if scene_kind in {WorkSceneKind.PLANT, WorkSceneKind.ROOM}
                    else "CENTERED"
                ),
                aspectRatio="16:9",
                focusPartId=subject_part_id,
            ),
            accessibilityNarrative=(
                candidate.accessibility_narrative
                if candidate is not None
                else (
                    f"画面位于{environment.label}，中心是{subject_label}。"
                    f"当{_joined(intent.inputs, '触发条件出现')}时，{behavior}，最终{result}。"
                )
            ),
            generation=generation or WorkSceneGeneration(
                source="LOCAL_COMPATIBILITY",
            ),
            sourceCanvasId=canvas_id,
            sourceCanvasRevision=canvas_revision,
        )

    def build_layout(
        self,
        spec: CanvasSpec,
        *,
        previous: CanvasLayout | None,
        updated_at: str,
    ) -> CanvasLayout:
        previous_positions = {
            item.node_id: item for item in (previous.positions if previous else [])
        }
        counters: dict[CanvasNodeKind, int] = {}
        positions: list[CanvasNodePosition] = []
        for node in spec.nodes:
            prior = previous_positions.get(node.id)
            if prior is not None:
                positions.append(prior)
                continue
            index = counters.get(node.kind, 0)
            counters[node.kind] = index + 1
            x, y = _automatic_position(node.kind, index)
            positions.append(
                CanvasNodePosition(
                    nodeId=node.id,
                    x=x,
                    y=y,
                    userPositioned=False,
                )
            )
        known = {node.id for node in spec.nodes}
        return CanvasLayout(
            id=(previous.id if previous is not None else f"layout_{_digest({'workId': spec.work_id})[:24]}"),
            workId=spec.work_id,
            canvasSpecId=spec.id,
            revision=(previous.revision + 1 if previous is not None else 1),
            algorithmVersion=_LAYOUT_ALGORITHM,
            positions=positions,
            viewport=(
                previous.viewport
                if previous is not None
                else CanvasViewport(x=0, y=0, zoom=1)
            ),
            collapsedNodeIds=(
                [node_id for node_id in previous.collapsed_node_ids if node_id in known]
                if previous is not None
                else []
            ),
            updatedAt=updated_at,
        )

    def project_existing(
        self,
        workspace: CreatorWorkspace,
    ) -> tuple[CanvasSpec, CanvasLayout]:
        created_at = workspace.updated_at
        source = (
            WorkIntentSource.IMPORT
            if workspace.legacy
            else WorkIntentSource.FREEFORM
        )
        seed = CanvasGenerationSeed(source=source)
        intent = self.understand_intent(
            workspace,
            seed,
            revision=1,
            created_at=created_at,
        )
        drafts, edge_drafts = self.extract_capabilities(intent)
        nodes, edges = self.match_packages(
            workspace.work_id,
            drafts,
            edge_drafts,
            catalog=[],
            selected_device_package_ids=[],
        )
        self.validate(nodes, edges)
        spec = self.build_spec(
            workspace,
            intent,
            nodes,
            edges,
            revision=1,
            created_at=created_at,
        )
        layout = self.build_layout(spec, previous=None, updated_at=created_at)
        return spec, layout


class WorkCanvasService:
    def __init__(
        self,
        data_dir: Path,
        *,
        compiler: CanvasCompiler | None = None,
        llm_planner: CanvasLLMPlanner | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._projects = ProjectRepository(self._data_dir)
        self._db_path = self._projects.db_path
        self._creator = CreatorRepository(self._data_dir)
        self._events = RealtimeEventStore(self._db_path)
        self._compiler = compiler or CanvasCompiler(self._data_dir)
        self._llm_planner = llm_planner or CanvasLLMPlanner(
            self._data_dir,
            credentials=credential_store_factory(),
            provider=provider_factory(),
        )
        self._owner_subject = current_owner_subject()
        self._owner_key = self._owner_subject or _LOCAL_OWNER

    @property
    def db_path(self) -> Path:
        return self._db_path

    def current(
        self,
        workspace: CreatorWorkspace,
    ) -> tuple[CanvasSpec, CanvasLayout, CanvasGeneration | None]:
        with self._connect() as conn:
            spec = self._latest_spec(conn, workspace.work_id)
            layout = self._latest_layout(conn, workspace.work_id)
            generation = self._latest_generation(conn, workspace.work_id)
        if spec is None:
            projected_spec, projected_layout = self._compiler.project_existing(workspace)
            return projected_spec, projected_layout, generation
        if layout is None or layout.canvas_spec_id != spec.id:
            layout = self._compiler.build_layout(
                spec,
                previous=layout,
                updated_at=spec.created_at,
            )
        return spec, layout, generation

    def confirm_proposal(
        self,
        work_id: str,
        request: ConfirmCanvasProposalRequest,
    ) -> CreatorWorkspace:
        """Confirm exactly the immutable canvas revision the user reviewed.

        This is an adapter onto the existing Creator goal/solution transaction;
        it does not create another plan or canvas fact store.
        """

        workspace = self._creator.workspace(work_id)
        spec, _layout, generation = self.current(workspace)
        if (
            spec.id != request.canvas_spec_id
            or spec.revision != request.expected_canvas_revision
        ):
            raise CanvasError(
                "CANVAS_PROPOSAL_STALE",
                "这版作品方案已经变化，请先查看最新结果再确认。",
                status_code=409,
            )
        if generation is not None and generation.status is not CanvasGenerationStatus.SUCCEEDED:
            raise CanvasError(
                "CANVAS_PROPOSAL_NOT_READY",
                "作品方案仍在整理，请等待当前结果完成后再确认。",
                status_code=409,
                retryable=True,
            )
        if (
            workspace.current_solution is not None
            and workspace.current_solution.status == "CONFIRMED"
            and self.solution_source_proposal(
                work_id,
                workspace.current_solution.id,
            ) == spec.id
        ):
            return workspace

        receipt = self._creator.project_conversation_draft(
            work_id,
            source_message_id=f"canvas:{spec.id}",
            source_turn_id=None,
            draft=_goal_draft_from_canvas(spec),
        )
        if receipt.status == "CONFLICT":
            raise CanvasError(
                "CANVAS_PROPOSAL_DRAFT_CONFLICT",
                "专业模式中还有未合并的目标草稿，请先比较后再确认这版方案。",
                status_code=409,
            )
        projected = self._creator.workspace(work_id)
        response = self._creator.execute(
            work_id,
            CreatorCommand.CONFIRM_SOLUTION,
            CreatorCommandRequest(
                baseProjectVersion=projected.project_version,
                idempotencyKey=request.idempotency_key,
                payload=_solution_payload_from_canvas(spec),
            ),
        )
        return response.workspace

    def solution_source_proposal(
        self,
        work_id: str,
        solution_id: str,
    ) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT source_proposal_id FROM creator_solution_revisions
                WHERE project_id = ? AND id = ?
                """,
                (work_id, solution_id),
            ).fetchone()
        if row is None or row["source_proposal_id"] is None:
            return None
        return str(row["source_proposal_id"])

    def import_spec(
        self,
        workspace: CreatorWorkspace,
        source_spec: CanvasSpec,
    ) -> tuple[CanvasSpec, CanvasLayout]:
        """Restore semantic canvas facts while deliberately rebuilding local layout."""

        work_id = workspace.work_id
        source_digest = _digest(
            {
                "targetWorkId": work_id,
                "sourceCanvas": source_spec.model_dump(by_alias=True, mode="json"),
            }
        )
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT payload_json FROM canvas_spec_revisions
                WHERE work_id = ? AND owner_key = ? AND source_digest = ?
                ORDER BY revision DESC LIMIT 1
                """,
                (work_id, self._owner_key, source_digest),
            ).fetchone()
            if existing is not None:
                spec = CanvasSpec.model_validate(
                    json.loads(str(existing["payload_json"]))
                )
                layout = self._latest_layout(conn, work_id)
                if layout is not None and layout.canvas_spec_id == spec.id:
                    return spec, layout

        created_at = _now()
        intent_digest = _digest(
            {
                "targetWorkId": work_id,
                "sourceIntentId": source_spec.work_intent.id,
                "sourceDigest": source_digest,
            }
        )
        intent = source_spec.work_intent.model_copy(
            update={
                "id": f"intent_{intent_digest[:24]}",
                "work_id": work_id,
                "revision": 1,
                "source": WorkIntentSource.IMPORT,
                "created_at": created_at,
            }
        )
        node_ids = {
            node.id: _imported_node_id(work_id, source_spec.work_id, node)
            for node in source_spec.nodes
        }
        nodes = [
            node.model_copy(
                update={
                    "id": node_ids[node.id],
                    "trust_state": (
                        CanvasTrustState.NEEDS_CONFIRMATION
                        if node.trust_state == CanvasTrustState.VERIFIED
                        else node.trust_state
                    ),
                    "evidence_refs": [],
                }
            )
            for node in source_spec.nodes
        ]
        edges = [
            edge.model_copy(
                update={
                    "id": _edge_id(
                        work_id,
                        edge.relation,
                        node_ids[edge.source_node_id],
                        node_ids[edge.target_node_id],
                    ),
                    "source_node_id": node_ids[edge.source_node_id],
                    "target_node_id": node_ids[edge.target_node_id],
                }
            )
            for edge in source_spec.edges
        ]
        self._compiler.validate(nodes, edges)
        spec = self._compiler.build_spec(
            workspace,
            intent,
            nodes,
            edges,
            revision=1,
            created_at=created_at,
        )
        layout = self._compiler.build_layout(
            spec,
            previous=None,
            updated_at=created_at,
        )
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO work_intent_revisions (
                  id, work_id, owner_key, revision, source,
                  payload_json, source_digest, created_at
                ) VALUES (?, ?, ?, 1, 'IMPORT', ?, ?, ?)
                """,
                (
                    intent.id,
                    work_id,
                    self._owner_key,
                    _dump(intent.model_dump(by_alias=True, mode="json")),
                    source_digest,
                    created_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO canvas_spec_revisions (
                  id, work_id, owner_key, revision, work_intent_revision_id,
                  payload_json, source_digest, created_at
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    spec.id,
                    work_id,
                    self._owner_key,
                    intent.id,
                    _dump(spec.model_dump(by_alias=True, mode="json")),
                    source_digest,
                    created_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO canvas_layouts (
                  id, work_id, owner_key, canvas_spec_revision_id,
                  revision, algorithm_version, payload_json,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    layout.id,
                    work_id,
                    self._owner_key,
                    spec.id,
                    layout.algorithm_version,
                    _dump(layout.model_dump(by_alias=True, mode="json")),
                    created_at,
                    created_at,
                ),
            )
            self._events.append_work_event(
                conn,
                work_id=work_id,
                event_type="work.canvas.generated",
                source_event_id=f"canvas-import:{work_id}:{source_digest}",
                payload={
                    "status": CanvasGenerationStatus.SUCCEEDED.value,
                    "canvasSpecId": spec.id,
                    "canvasRevision": spec.revision,
                    "layoutRevision": layout.revision,
                    "sceneSchemaVersion": spec.scene.schema_version if spec.scene else None,
                    "sceneKind": spec.scene.kind.value if spec.scene else None,
                    "imported": True,
                    "progress": 100,
                },
            )
        return spec, layout

    def start_generation(
        self,
        work_id: str,
        request: StartCanvasGenerationRequest,
    ) -> CanvasGeneration:
        self._creator.workspace(work_id)
        seed = CanvasGenerationSeed.model_validate(
            request.model_dump(by_alias=True, mode="json", exclude={"idempotency_key"})
        )
        payload = seed.model_dump(by_alias=True, mode="json")
        request_digest = _digest(payload)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT * FROM canvas_generations
                WHERE work_id = ? AND owner_key = ? AND idempotency_key = ?
                """,
                (work_id, self._owner_key, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["request_digest"]) != request_digest:
                    raise CanvasError(
                        "CANVAS_GENERATION_IDEMPOTENCY_CONFLICT",
                        "该生成请求标识已经用于不同内容。",
                        status_code=409,
                    )
                return _generation_from_row(existing)
            now = _now()
            generation_id = f"canvasgen_{uuid.uuid4().hex}"
            conn.execute(
                """
                INSERT INTO canvas_generations (
                  id, work_id, owner_key, idempotency_key, request_digest,
                  seed_json, status, current_step, completed_steps_json,
                  progress, natural_status, error_code, retryable,
                  intent_revision_id, canvas_spec_revision_id,
                  created_at, started_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'QUEUED', NULL, '[]', 0, ?,
                          NULL, 0, NULL, NULL, ?, NULL, ?, NULL)
                """,
                (
                    generation_id,
                    work_id,
                    self._owner_key,
                    request.idempotency_key,
                    request_digest,
                    _dump(payload),
                    "作品画面已排队，等待当前作品模型分析。",
                    now,
                    now,
                ),
            )
            self._append_generation_event(
                conn,
                work_id=work_id,
                generation_id=generation_id,
                event_type="work.canvas.generation.changed",
                source_suffix="queued",
                payload={
                    "generationId": generation_id,
                    "status": CanvasGenerationStatus.QUEUED.value,
                    "progress": 0,
                },
            )
            row = self._generation_row(conn, work_id, generation_id)
            return _generation_from_row(row)

    def run_generation(self, work_id: str, generation_id: str) -> CanvasGeneration:
        workspace = self._creator.workspace(work_id)
        generation, should_run = self._mark_running(work_id, generation_id)
        if not should_run:
            return generation
        try:
            seed = self._seed_for_generation(work_id, generation_id)
            intent_revision, spec_revision = self._next_revisions(work_id)
            created_at = _now()
            candidate, runtime_selection = self._llm_planner.generate(
                generation_id=generation_id,
                work_name=workspace.name,
                semantic_context=_workspace_semantic_context(workspace),
                environment_hint=seed.environment_hint,
                network_preference=seed.network_preference,
                reference_count=len(seed.reference_names),
                selected_inventory_count=len(seed.selected_inventory_item_ids),
            )
            intent = self._compiler.intent_from_candidate(
                workspace,
                seed,
                candidate,
                revision=intent_revision,
                created_at=created_at,
            )
            self._complete_step(
                work_id,
                generation_id,
                CanvasGenerationStep.UNDERSTAND_INTENT,
            )
            drafts, edge_drafts = self._compiler.extract_capabilities(intent)
            self._complete_step(
                work_id,
                generation_id,
                CanvasGenerationStep.EXTRACT_CAPABILITIES,
            )
            catalog = self._compiler.package_catalog()
            selected_ids = self._compiler.selected_device_package_ids(
                seed.selected_inventory_item_ids
            )
            nodes, edges = self._compiler.match_packages(
                work_id,
                drafts,
                edge_drafts,
                catalog,
                selected_ids,
            )
            self._complete_step(
                work_id,
                generation_id,
                CanvasGenerationStep.MATCH_PACKAGES,
            )
            self._compiler.validate(nodes, edges)
            self._complete_step(
                work_id,
                generation_id,
                CanvasGenerationStep.VALIDATE_LOCALLY,
            )
            spec = self._compiler.build_spec(
                workspace,
                intent,
                nodes,
                edges,
                revision=spec_revision,
                created_at=created_at,
                scene_candidate=candidate.scene,
                runtime_selection=runtime_selection,
            )
            with self._connect() as conn:
                previous_layout = self._latest_layout(conn, work_id)
            layout = self._compiler.build_layout(
                spec,
                previous=previous_layout,
                updated_at=_now(),
            )
            return self._finish_success(
                work_id,
                generation_id,
                intent=intent,
                spec=spec,
                layout=layout,
            )
        except CanvasGenerationCanceled:
            return self.get_generation(work_id, generation_id)
        except CanvasError as exc:
            return self._finish_failure(
                work_id,
                generation_id,
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
            )
        except StructuredLLMError as exc:
            return self._finish_failure(
                work_id,
                generation_id,
                code=f"CANVAS_LLM_{exc.error.code.value}",
                message=exc.error.message,
                retryable=(
                    exc.error.retryable
                    or exc.error.code is LLMErrorCode.CONFIG_MISSING
                ),
            )
        except ProviderSettingsConflictError as exc:
            return self._finish_failure(
                work_id,
                generation_id,
                code="CANVAS_LLM_CONFIGURATION_BLOCKED",
                message=str(exc),
                retryable=True,
            )
        except Exception:
            return self._finish_failure(
                work_id,
                generation_id,
                code="CANVAS_COMPILATION_FAILED",
                message="本地作品地图生成失败，可以安全重试。",
                retryable=True,
            )

    def get_generation(self, work_id: str, generation_id: str) -> CanvasGeneration:
        self._creator.workspace(work_id)
        with self._connect() as conn:
            return _generation_from_row(
                self._generation_row(conn, work_id, generation_id)
            )

    def cancel_generation(
        self,
        work_id: str,
        generation_id: str,
        request: CanvasGenerationCommandRequest,
    ) -> CanvasGeneration:
        self._creator.workspace(work_id)
        request_digest = _digest({"generationId": generation_id})
        replay = self._command_replay(
            work_id,
            operation="CANCEL",
            idempotency_key=request.idempotency_key,
            request_digest=request_digest,
        )
        if replay is not None:
            return CanvasGeneration.model_validate(replay["generation"])
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._generation_row(conn, work_id, generation_id)
            status = CanvasGenerationStatus(str(row["status"]))
            if status in {CanvasGenerationStatus.SUCCEEDED, CanvasGenerationStatus.FAILED}:
                raise CanvasError(
                    "CANVAS_GENERATION_NOT_CANCELABLE",
                    "已结束的作品地图生成不能取消。",
                    status_code=409,
                )
            now = _now()
            if status is not CanvasGenerationStatus.CANCELED:
                conn.execute(
                    """
                    UPDATE canvas_generations
                    SET status = 'CANCELED', natural_status = ?, retryable = 0,
                        updated_at = ?, completed_at = ?
                    WHERE id = ? AND work_id = ? AND owner_key = ?
                    """,
                    ("用户已取消作品地图生成。", now, now, generation_id, work_id, self._owner_key),
                )
            updated = _generation_from_row(
                self._generation_row(conn, work_id, generation_id)
            )
            self._insert_command(
                conn,
                work_id=work_id,
                generation_id=generation_id,
                operation="CANCEL",
                idempotency_key=request.idempotency_key,
                request_digest=request_digest,
                result={"generation": updated.model_dump(by_alias=True, mode="json")},
            )
            self._append_generation_event(
                conn,
                work_id=work_id,
                generation_id=generation_id,
                event_type="work.canvas.generation.changed",
                source_suffix=f"cancel:{request.idempotency_key}",
                payload={
                    "generationId": generation_id,
                    "status": CanvasGenerationStatus.CANCELED.value,
                    "progress": updated.progress,
                },
            )
            return updated

    def retry_generation(
        self,
        work_id: str,
        generation_id: str,
        request: CanvasGenerationCommandRequest,
    ) -> CanvasGeneration:
        self._creator.workspace(work_id)
        request_digest = _digest({"generationId": generation_id})
        replay = self._command_replay(
            work_id,
            operation="RETRY",
            idempotency_key=request.idempotency_key,
            request_digest=request_digest,
        )
        if replay is not None:
            return CanvasGeneration.model_validate(replay["generation"])
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._generation_row(conn, work_id, generation_id)
            if str(row["status"]) != CanvasGenerationStatus.FAILED.value or not bool(row["retryable"]):
                raise CanvasError(
                    "CANVAS_GENERATION_NOT_RETRYABLE",
                    "只有可恢复失败的作品地图生成可以重试。",
                    status_code=409,
                )
            now = _now()
            conn.execute(
                """
                UPDATE canvas_generations
                SET status = 'QUEUED', current_step = NULL,
                    completed_steps_json = '[]', progress = 0,
                    natural_status = ?, error_code = NULL, retryable = 0,
                    started_at = NULL, updated_at = ?, completed_at = NULL
                WHERE id = ? AND work_id = ? AND owner_key = ?
                """,
                ("作品地图已重新排队。", now, generation_id, work_id, self._owner_key),
            )
            updated = _generation_from_row(
                self._generation_row(conn, work_id, generation_id)
            )
            self._insert_command(
                conn,
                work_id=work_id,
                generation_id=generation_id,
                operation="RETRY",
                idempotency_key=request.idempotency_key,
                request_digest=request_digest,
                result={"generation": updated.model_dump(by_alias=True, mode="json")},
            )
            self._append_generation_event(
                conn,
                work_id=work_id,
                generation_id=generation_id,
                event_type="work.canvas.generation.changed",
                source_suffix=f"retry:{request.idempotency_key}",
                payload={
                    "generationId": generation_id,
                    "status": CanvasGenerationStatus.QUEUED.value,
                    "progress": 0,
                },
            )
            return updated

    def save_layout(
        self,
        work_id: str,
        request: SaveCanvasLayoutRequest,
    ) -> CanvasLayout:
        self._creator.workspace(work_id)
        payload = request.model_dump(by_alias=True, mode="json", exclude={"idempotency_key"})
        request_digest = _digest(payload)
        replay = self._command_replay(
            work_id,
            operation="SAVE_LAYOUT",
            idempotency_key=request.idempotency_key,
            request_digest=request_digest,
        )
        if replay is not None:
            return CanvasLayout.model_validate(replay["layout"])
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            spec = self._latest_spec(conn, work_id)
            layout = self._latest_layout(conn, work_id)
            if spec is None or layout is None:
                raise CanvasError(
                    "CANVAS_LAYOUT_NOT_READY",
                    "作品地图尚未生成，暂时不能保存布局。",
                    status_code=409,
                )
            if layout.revision != request.expected_revision:
                raise CanvasError(
                    "CANVAS_LAYOUT_REVISION_CONFLICT",
                    "作品地图布局已经更新，请刷新后重试。",
                    status_code=409,
                )
            requested_ids = [item.node_id for item in request.positions]
            known_ids = {node.id for node in spec.nodes}
            if len(requested_ids) != len(set(requested_ids)) or set(requested_ids) != known_ids:
                raise CanvasError(
                    "CANVAS_LAYOUT_NODE_SET_INVALID",
                    "布局必须且只能包含当前作品地图的全部节点。",
                    status_code=422,
                )
            if not set(request.collapsed_node_ids).issubset(known_ids):
                raise CanvasError(
                    "CANVAS_LAYOUT_COLLAPSED_NODE_INVALID",
                    "折叠列表包含未知节点。",
                    status_code=422,
                )
            now = _now()
            updated = CanvasLayout(
                id=layout.id,
                workId=work_id,
                canvasSpecId=spec.id,
                revision=layout.revision + 1,
                algorithmVersion=layout.algorithm_version,
                positions=request.positions,
                viewport=request.viewport,
                collapsedNodeIds=_unique(request.collapsed_node_ids),
                updatedAt=now,
            )
            conn.execute(
                """
                UPDATE canvas_layouts
                SET revision = ?, payload_json = ?, updated_at = ?
                WHERE id = ? AND work_id = ? AND owner_key = ? AND revision = ?
                """,
                (
                    updated.revision,
                    _dump(updated.model_dump(by_alias=True, mode="json")),
                    now,
                    layout.id,
                    work_id,
                    self._owner_key,
                    layout.revision,
                ),
            )
            if conn.total_changes < 1:
                raise CanvasError(
                    "CANVAS_LAYOUT_REVISION_CONFLICT",
                    "作品地图布局已经更新，请刷新后重试。",
                    status_code=409,
                )
            self._insert_command(
                conn,
                work_id=work_id,
                generation_id=None,
                operation="SAVE_LAYOUT",
                idempotency_key=request.idempotency_key,
                request_digest=request_digest,
                result={"layout": updated.model_dump(by_alias=True, mode="json")},
            )
            self._events.append_work_event(
                conn,
                work_id=work_id,
                event_type="work.canvas.layout.changed",
                source_event_id=f"canvas-layout:{work_id}:{request.idempotency_key}",
                payload={
                    "canvasSpecId": spec.id,
                    "layoutRevision": updated.revision,
                    "changeKind": "USER_LAYOUT",
                },
            )
            return updated

    def recover_interrupted(self) -> int:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT * FROM canvas_generations WHERE status = 'RUNNING'"
            ).fetchall()
            now = _now()
            for row in rows:
                conn.execute(
                    """
                    UPDATE canvas_generations
                    SET status = 'QUEUED', current_step = NULL,
                        completed_steps_json = '[]', progress = 0,
                        natural_status = ?, error_code = NULL, retryable = 0,
                        started_at = NULL, updated_at = ?, completed_at = NULL
                    WHERE id = ? AND status = 'RUNNING'
                    """,
                    ("本地服务重启后已安全恢复排队。", now, str(row["id"])),
                )
                self._events.append_work_event(
                    conn,
                    work_id=str(row["work_id"]),
                    event_type="work.canvas.generation.changed",
                    source_event_id=f"canvas-generation:{row['id']}:process-recovery",
                    payload={
                        "generationId": str(row["id"]),
                        "status": CanvasGenerationStatus.QUEUED.value,
                        "progress": 0,
                        "reason": "PROCESS_RESTART_RECOVERY",
                    },
                )
            return len(rows)

    def _mark_running(
        self,
        work_id: str,
        generation_id: str,
    ) -> tuple[CanvasGeneration, bool]:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._generation_row(conn, work_id, generation_id)
            status = CanvasGenerationStatus(str(row["status"]))
            if status in {CanvasGenerationStatus.SUCCEEDED, CanvasGenerationStatus.RUNNING}:
                return _generation_from_row(row), False
            if status is CanvasGenerationStatus.CANCELED:
                raise CanvasGenerationCanceled()
            if status is CanvasGenerationStatus.FAILED:
                raise CanvasError(
                    "CANVAS_GENERATION_RETRY_REQUIRED",
                    "请先确认重试，再重新生成作品地图。",
                    status_code=409,
                )
            active = conn.execute(
                """
                SELECT id FROM canvas_generations
                WHERE work_id = ? AND owner_key = ? AND status = 'RUNNING' AND id != ?
                LIMIT 1
                """,
                (work_id, self._owner_key, generation_id),
            ).fetchone()
            if active is not None:
                raise CanvasError(
                    "CANVAS_GENERATION_BUSY",
                    "这件作品已有地图生成正在运行。",
                    status_code=409,
                    retryable=True,
                )
            now = _now()
            first_step = _GENERATION_STEPS[0]
            conn.execute(
                """
                UPDATE canvas_generations
                SET status = 'RUNNING', current_step = ?, progress = 1,
                    natural_status = ?, started_at = COALESCE(started_at, ?),
                    updated_at = ?, completed_at = NULL
                WHERE id = ? AND work_id = ? AND owner_key = ? AND status = 'QUEUED'
                """,
                (
                    first_step.value,
                    _STEP_STATUS[first_step],
                    now,
                    now,
                    generation_id,
                    work_id,
                    self._owner_key,
                ),
            )
            self._append_generation_event(
                conn,
                work_id=work_id,
                generation_id=generation_id,
                event_type="work.canvas.generation.changed",
                source_suffix="running:1",
                payload={
                    "generationId": generation_id,
                    "status": CanvasGenerationStatus.RUNNING.value,
                    "step": first_step.value,
                    "progress": 1,
                },
            )
            return _generation_from_row(
                self._generation_row(conn, work_id, generation_id)
            ), True

    def _complete_step(
        self,
        work_id: str,
        generation_id: str,
        step: CanvasGenerationStep,
    ) -> CanvasGeneration:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._generation_row(conn, work_id, generation_id)
            if str(row["status"]) == CanvasGenerationStatus.CANCELED.value:
                raise CanvasGenerationCanceled()
            if str(row["status"]) != CanvasGenerationStatus.RUNNING.value:
                raise CanvasError(
                    "CANVAS_GENERATION_NOT_RUNNING",
                    "作品地图生成已不在运行状态。",
                    status_code=409,
                )
            completed = [
                CanvasGenerationStep(value)
                for value in json.loads(str(row["completed_steps_json"]))
            ]
            if step not in completed:
                completed.append(step)
            step_index = _GENERATION_STEPS.index(step)
            next_step = (
                _GENERATION_STEPS[step_index + 1]
                if step_index + 1 < len(_GENERATION_STEPS)
                else None
            )
            progress = _STEP_PROGRESS[step]
            natural_status = (
                _STEP_STATUS[next_step]
                if next_step is not None
                else "作品画面已经生成。"
            )
            conn.execute(
                """
                UPDATE canvas_generations
                SET current_step = ?, completed_steps_json = ?, progress = ?,
                    natural_status = ?, updated_at = ?
                WHERE id = ? AND work_id = ? AND owner_key = ? AND status = 'RUNNING'
                """,
                (
                    next_step.value if next_step is not None else None,
                    _dump([item.value for item in completed]),
                    progress,
                    natural_status,
                    _now(),
                    generation_id,
                    work_id,
                    self._owner_key,
                ),
            )
            self._append_generation_event(
                conn,
                work_id=work_id,
                generation_id=generation_id,
                event_type="work.canvas.generation.progress",
                source_suffix=f"step:{step.value}",
                payload={
                    "generationId": generation_id,
                    "status": CanvasGenerationStatus.RUNNING.value,
                    "completedStep": step.value,
                    "nextStep": next_step.value if next_step is not None else None,
                    "progress": progress,
                },
            )
            return _generation_from_row(
                self._generation_row(conn, work_id, generation_id)
            )

    def _finish_success(
        self,
        work_id: str,
        generation_id: str,
        *,
        intent: WorkIntent,
        spec: CanvasSpec,
        layout: CanvasLayout,
    ) -> CanvasGeneration:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._generation_row(conn, work_id, generation_id)
            if str(row["status"]) == CanvasGenerationStatus.CANCELED.value:
                raise CanvasGenerationCanceled()
            if str(row["status"]) != CanvasGenerationStatus.RUNNING.value:
                raise CanvasError(
                    "CANVAS_GENERATION_NOT_RUNNING",
                    "作品地图生成已不在运行状态。",
                    status_code=409,
                )
            source_digest = _canvas_source_digest(
                intent,
                spec,
                seed=json.loads(str(row["seed_json"])),
            )
            latest_spec_row = conn.execute(
                """
                SELECT source_digest, payload_json FROM canvas_spec_revisions
                WHERE work_id = ? AND owner_key = ?
                ORDER BY revision DESC LIMIT 1
                """,
                (work_id, self._owner_key),
            ).fetchone()
            existing_layout = self._latest_layout(conn, work_id)
            if (
                latest_spec_row is not None
                and str(latest_spec_row["source_digest"]) == source_digest
                and existing_layout is not None
            ):
                existing_spec = CanvasSpec.model_validate(
                    json.loads(str(latest_spec_row["payload_json"]))
                )
                if existing_layout.canvas_spec_id == existing_spec.id:
                    completed = [step.value for step in _GENERATION_STEPS]
                    now = _now()
                    conn.execute(
                        """
                        UPDATE canvas_generations
                        SET status = 'SUCCEEDED', current_step = NULL,
                            completed_steps_json = ?, progress = 100,
                            natural_status = ?, error_code = NULL, retryable = 0,
                            intent_revision_id = ?, canvas_spec_revision_id = ?,
                            updated_at = ?, completed_at = ?
                        WHERE id = ? AND work_id = ? AND owner_key = ?
                          AND status = 'RUNNING'
                        """,
                        (
                            _dump(completed),
                            existing_spec.natural_status,
                            existing_spec.work_intent.id,
                            existing_spec.id,
                            now,
                            now,
                            generation_id,
                            work_id,
                            self._owner_key,
                        ),
                    )
                    self._append_generation_event(
                        conn,
                        work_id=work_id,
                        generation_id=generation_id,
                        event_type="work.canvas.generated",
                        source_suffix="succeeded:reused",
                        payload={
                            "generationId": generation_id,
                            "status": CanvasGenerationStatus.SUCCEEDED.value,
                            "canvasSpecId": existing_spec.id,
                            "canvasRevision": existing_spec.revision,
                            "layoutRevision": existing_layout.revision,
                            "sceneSchemaVersion": (
                                existing_spec.scene.schema_version
                                if existing_spec.scene
                                else None
                            ),
                            "sceneKind": (
                                existing_spec.scene.kind.value
                                if existing_spec.scene
                                else None
                            ),
                            "reused": True,
                            "progress": 100,
                        },
                    )
                    return _generation_from_row(
                        self._generation_row(conn, work_id, generation_id)
                    )
            conn.execute(
                """
                INSERT INTO work_intent_revisions (
                  id, work_id, owner_key, revision, source,
                  payload_json, source_digest, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    intent.id,
                    work_id,
                    self._owner_key,
                    intent.revision,
                    intent.source.value,
                    _dump(intent.model_dump(by_alias=True, mode="json")),
                    source_digest,
                    intent.created_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO canvas_spec_revisions (
                  id, work_id, owner_key, revision, work_intent_revision_id,
                  payload_json, source_digest, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    spec.id,
                    work_id,
                    self._owner_key,
                    spec.revision,
                    intent.id,
                    _dump(spec.model_dump(by_alias=True, mode="json")),
                    source_digest,
                    spec.created_at,
                ),
            )
            existing_layout = conn.execute(
                "SELECT id FROM canvas_layouts WHERE work_id = ? AND owner_key = ?",
                (work_id, self._owner_key),
            ).fetchone()
            if existing_layout is None:
                conn.execute(
                    """
                    INSERT INTO canvas_layouts (
                      id, work_id, owner_key, canvas_spec_revision_id,
                      revision, algorithm_version, payload_json,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        layout.id,
                        work_id,
                        self._owner_key,
                        spec.id,
                        layout.revision,
                        layout.algorithm_version,
                        _dump(layout.model_dump(by_alias=True, mode="json")),
                        layout.updated_at,
                        layout.updated_at,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE canvas_layouts
                    SET canvas_spec_revision_id = ?, revision = ?,
                        algorithm_version = ?, payload_json = ?, updated_at = ?
                    WHERE work_id = ? AND owner_key = ?
                    """,
                    (
                        spec.id,
                        layout.revision,
                        layout.algorithm_version,
                        _dump(layout.model_dump(by_alias=True, mode="json")),
                        layout.updated_at,
                        work_id,
                        self._owner_key,
                    ),
                )
            completed = [step.value for step in _GENERATION_STEPS]
            now = _now()
            conn.execute(
                """
                UPDATE canvas_generations
                SET status = 'SUCCEEDED', current_step = NULL,
                    completed_steps_json = ?, progress = 100,
                    natural_status = ?, error_code = NULL, retryable = 0,
                    intent_revision_id = ?, canvas_spec_revision_id = ?,
                    updated_at = ?, completed_at = ?
                WHERE id = ? AND work_id = ? AND owner_key = ? AND status = 'RUNNING'
                """,
                (
                    _dump(completed),
                    spec.natural_status,
                    intent.id,
                    spec.id,
                    now,
                    now,
                    generation_id,
                    work_id,
                    self._owner_key,
                ),
            )
            self._append_generation_event(
                conn,
                work_id=work_id,
                generation_id=generation_id,
                event_type="work.canvas.generated",
                source_suffix="succeeded",
                payload={
                    "generationId": generation_id,
                    "status": CanvasGenerationStatus.SUCCEEDED.value,
                    "canvasSpecId": spec.id,
                    "canvasRevision": spec.revision,
                    "layoutRevision": layout.revision,
                    "sceneSchemaVersion": spec.scene.schema_version if spec.scene else None,
                    "sceneKind": spec.scene.kind.value if spec.scene else None,
                    "progress": 100,
                },
            )
            return _generation_from_row(
                self._generation_row(conn, work_id, generation_id)
            )

    def _finish_failure(
        self,
        work_id: str,
        generation_id: str,
        *,
        code: str,
        message: str,
        retryable: bool,
    ) -> CanvasGeneration:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._generation_row(conn, work_id, generation_id)
            if str(row["status"]) == CanvasGenerationStatus.CANCELED.value:
                return _generation_from_row(row)
            if str(row["status"]) != CanvasGenerationStatus.RUNNING.value:
                return _generation_from_row(row)
            now = _now()
            conn.execute(
                """
                UPDATE canvas_generations
                SET status = 'FAILED', natural_status = ?, error_code = ?,
                    retryable = ?, updated_at = ?, completed_at = ?
                WHERE id = ? AND work_id = ? AND owner_key = ?
                """,
                (message, code, int(retryable), now, now, generation_id, work_id, self._owner_key),
            )
            self._append_generation_event(
                conn,
                work_id=work_id,
                generation_id=generation_id,
                event_type="work.canvas.generation.changed",
                source_suffix=f"failed:{code}",
                payload={
                    "generationId": generation_id,
                    "status": CanvasGenerationStatus.FAILED.value,
                    "errorCode": code,
                    "retryable": retryable,
                    "progress": int(row["progress"]),
                },
            )
            return _generation_from_row(
                self._generation_row(conn, work_id, generation_id)
            )

    def _next_revisions(self, work_id: str) -> tuple[int, int]:
        with self._connect() as conn:
            intent = conn.execute(
                """
                SELECT COALESCE(MAX(revision), 0) + 1
                FROM work_intent_revisions WHERE work_id = ? AND owner_key = ?
                """,
                (work_id, self._owner_key),
            ).fetchone()
            spec = conn.execute(
                """
                SELECT COALESCE(MAX(revision), 0) + 1
                FROM canvas_spec_revisions WHERE work_id = ? AND owner_key = ?
                """,
                (work_id, self._owner_key),
            ).fetchone()
        return int(intent[0]), int(spec[0])

    def _seed_for_generation(
        self,
        work_id: str,
        generation_id: str,
    ) -> CanvasGenerationSeed:
        with self._connect() as conn:
            row = self._generation_row(conn, work_id, generation_id)
        return CanvasGenerationSeed.model_validate(json.loads(str(row["seed_json"])))

    def _command_replay(
        self,
        work_id: str,
        *,
        operation: str,
        idempotency_key: str,
        request_digest: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT request_digest, result_json FROM canvas_commands
                WHERE work_id = ? AND owner_key = ? AND operation = ?
                  AND idempotency_key = ?
                """,
                (work_id, self._owner_key, operation, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        if str(row["request_digest"]) != request_digest:
            raise CanvasError(
                "CANVAS_COMMAND_IDEMPOTENCY_CONFLICT",
                "该操作标识已经用于不同内容。",
                status_code=409,
            )
        value = json.loads(str(row["result_json"]))
        if not isinstance(value, dict):
            raise CanvasError(
                "CANVAS_COMMAND_RESULT_INVALID",
                "已保存的操作结果无效。",
                status_code=500,
            )
        return value

    def _insert_command(
        self,
        conn: sqlite3.Connection,
        *,
        work_id: str,
        generation_id: str | None,
        operation: str,
        idempotency_key: str,
        request_digest: str,
        result: dict[str, Any],
    ) -> None:
        conn.execute(
            """
            INSERT INTO canvas_commands (
              id, work_id, owner_key, generation_id, operation,
              idempotency_key, request_digest, result_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"canvascmd_{uuid.uuid4().hex}",
                work_id,
                self._owner_key,
                generation_id,
                operation,
                idempotency_key,
                request_digest,
                _dump(result),
                _now(),
            ),
        )

    def _append_generation_event(
        self,
        conn: sqlite3.Connection,
        *,
        work_id: str,
        generation_id: str,
        event_type: str,
        source_suffix: str,
        payload: dict[str, Any],
    ) -> None:
        self._events.append_work_event(
            conn,
            work_id=work_id,
            event_type=event_type,
            source_event_id=f"canvas-generation:{generation_id}:{source_suffix}",
            payload=payload,
        )

    def _generation_row(
        self,
        conn: sqlite3.Connection,
        work_id: str,
        generation_id: str,
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT * FROM canvas_generations
            WHERE id = ? AND work_id = ? AND owner_key = ?
            """,
            (generation_id, work_id, self._owner_key),
        ).fetchone()
        if row is None:
            raise CanvasError(
                "CANVAS_GENERATION_NOT_FOUND",
                "作品地图生成记录不存在。",
                status_code=404,
            )
        return row

    def _latest_generation(
        self,
        conn: sqlite3.Connection,
        work_id: str,
    ) -> CanvasGeneration | None:
        row = conn.execute(
            """
            SELECT * FROM canvas_generations
            WHERE work_id = ? AND owner_key = ?
            ORDER BY created_at DESC, id DESC LIMIT 1
            """,
            (work_id, self._owner_key),
        ).fetchone()
        return _generation_from_row(row) if row is not None else None

    def _latest_spec(
        self,
        conn: sqlite3.Connection,
        work_id: str,
    ) -> CanvasSpec | None:
        row = conn.execute(
            """
            SELECT payload_json FROM canvas_spec_revisions
            WHERE work_id = ? AND owner_key = ?
            ORDER BY revision DESC LIMIT 1
            """,
            (work_id, self._owner_key),
        ).fetchone()
        return (
            CanvasSpec.model_validate(json.loads(str(row["payload_json"])))
            if row is not None
            else None
        )

    def _latest_layout(
        self,
        conn: sqlite3.Connection,
        work_id: str,
    ) -> CanvasLayout | None:
        row = conn.execute(
            """
            SELECT payload_json FROM canvas_layouts
            WHERE work_id = ? AND owner_key = ?
            """,
            (work_id, self._owner_key),
        ).fetchone()
        return (
            CanvasLayout.model_validate(json.loads(str(row["payload_json"])))
            if row is not None
            else None
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def derived_canvas_idempotency_key(create_key: str) -> str:
    return f"canvas-create:{hashlib.sha256(create_key.encode('utf-8')).hexdigest()[:32]}"


def _generation_from_row(row: sqlite3.Row) -> CanvasGeneration:
    return CanvasGeneration(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        status=CanvasGenerationStatus(str(row["status"])),
        currentStep=(
            CanvasGenerationStep(str(row["current_step"]))
            if row["current_step"] is not None
            else None
        ),
        completedSteps=[
            CanvasGenerationStep(value)
            for value in json.loads(str(row["completed_steps_json"]))
        ],
        progress=int(row["progress"]),
        naturalStatus=str(row["natural_status"]),
        errorCode=str(row["error_code"]) if row["error_code"] is not None else None,
        retryable=bool(row["retryable"]),
        canvasSpecId=(
            str(row["canvas_spec_revision_id"])
            if row["canvas_spec_revision_id"] is not None
            else None
        ),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
        completedAt=str(row["completed_at"]) if row["completed_at"] is not None else None,
    )


def _automatic_position(kind: CanvasNodeKind, index: int) -> tuple[float, float]:
    origins: dict[CanvasNodeKind, tuple[float, float, float, float]] = {
        CanvasNodeKind.WORK: (430, 280, 0, 0),
        CanvasNodeKind.INPUT: (40, 120, 0, 150),
        CanvasNodeKind.BEHAVIOR: (350, 40, 0, 150),
        CanvasNodeKind.OUTPUT: (760, 130, 0, 150),
        CanvasNodeKind.PHYSICAL_ACTION: (760, 390, 0, 150),
        CanvasNodeKind.SERVICE: (760, 20, 190, 0),
        CanvasNodeKind.DEVICE: (350, 540, 190, 0),
        CanvasNodeKind.POWER: (40, 540, 190, 0),
        CanvasNodeKind.STRUCTURE: (760, 570, 190, 0),
    }
    x, y, dx, dy = origins[kind]
    return x + dx * index, y + dy * index


def _node_id(work_id: str, semantic_key: str) -> str:
    normalized = re.sub(r"[^a-z0-9:-]+", "-", semantic_key.casefold()).strip("-")
    if not normalized:
        normalized = hashlib.sha256(semantic_key.encode("utf-8")).hexdigest()[:16]
    return f"{work_id}:{normalized}"


def _imported_node_id(
    work_id: str,
    source_work_id: str,
    node: CanvasNode,
) -> str:
    prefix = f"{source_work_id}:"
    semantic_key = (
        node.id[len(prefix) :]
        if node.id.startswith(prefix) and len(node.id) > len(prefix)
        else f"{node.kind.value}:{node.capability}:{node.title}"
    )
    return _node_id(work_id, semantic_key)


def _edge_id(work_id: str, relation: str, source_id: str, target_id: str) -> str:
    digest = hashlib.sha256(
        f"{work_id}\0{relation}\0{source_id}\0{target_id}".encode("utf-8")
    ).hexdigest()[:20]
    return f"{work_id}:edge:{digest}"


def _workspace_semantic_context(workspace: CreatorWorkspace) -> str:
    """Build a bounded current Work basis without replacing the initial idea."""

    parts = [workspace.initial_idea.strip()[:1600]]
    goal = workspace.current_goal
    if goal is not None:
        parts.extend(
            [
                goal.statement.strip()[:800],
                goal.observable_behavior.strip()[:600],
                "；".join(goal.constraints[:12])[:500],
            ]
        )
    solution = workspace.current_solution
    if solution is not None:
        parts.extend(
            [
                solution.summary.strip()[:800],
                solution.logic.strip()[:800],
                solution.hardware.strip()[:800],
                solution.software.strip()[:500],
                solution.structure.strip()[:500],
                solution.safety.strip()[:500],
            ]
        )
    unique_parts = _unique(part for part in parts if part)
    context = "\n".join(unique_parts).strip()
    return context[:4000] or workspace.name[:120]


def _scene_generation(
    selection: RuntimeModelSelection | None,
) -> WorkSceneGeneration:
    if selection is None:
        return WorkSceneGeneration(source="LOCAL_COMPATIBILITY")
    return WorkSceneGeneration(
        source="PROJECT_LLM",
        providerConfigurationRevisionId=selection.provider_configuration_revision_id,
        routingProfileRevisionId=selection.routing_profile_revision_id,
        model=str(selection.model),
    )


def _bounded_unique(values: Iterable[str], limit: int) -> list[str]:
    return _unique(value.strip() for value in values if value.strip())[:limit]


def _goal_draft_from_canvas(spec: CanvasSpec) -> ConversationProjectDraftV1:
    intent = spec.work_intent
    behavior = "；".join(intent.behaviors) or intent.summary
    criteria = intent.outputs or ["第一版可观察结果与作品目标一致"]
    return ConversationProjectDraftV1(
        useScenario=intent.summary,
        observableBehavior=behavior,
        constraints=intent.constraints,
        successCriteria=criteria,
        missingFields=intent.unknowns,
    )


def _solution_payload_from_canvas(spec: CanvasSpec) -> dict[str, object]:
    intent = spec.work_intent
    hardware_kinds = {
        CanvasNodeKind.INPUT,
        CanvasNodeKind.OUTPUT,
        CanvasNodeKind.PHYSICAL_ACTION,
        CanvasNodeKind.DEVICE,
        CanvasNodeKind.POWER,
    }
    hardware = [node.title for node in spec.nodes if node.kind in hardware_kinds]
    service = [node.title for node in spec.nodes if node.kind is CanvasNodeKind.SERVICE]
    structure = [node.title for node in spec.nodes if node.kind is CanvasNodeKind.STRUCTURE]
    inputs = "、".join(intent.inputs) or "用户触发"
    outputs = "、".join(intent.outputs) or "可观察结果"
    scenarios = [
        {
            "title": f"确认{output}",
            "required": True,
            "simulationExpected": f"在数字版本中触发{inputs}后，可以观察到{output}。",
            "physicalExpected": f"连接真实设备后，由用户观察并确认{output}。",
        }
        for output in (intent.outputs or ["第一版核心结果"])
    ]
    return {
        "summary": intent.summary,
        "logic": "；".join(intent.behaviors) or "先形成输入、判断和结果的最短闭环。",
        "hardware": "、".join(hardware) or "第一版先使用数字实现，真实设备稍后选择。",
        "software": (
            "；".join([*intent.behaviors, *service])
            or "使用本地优先的受控逻辑形成可观察结果。"
        ),
        "structure": "、".join(structure) or "第一版暂无必须结构，按作品需要再展开。",
        "simulation": f"先在数字版本中检查“{inputs} → {outputs}”是否符合预期。",
        "safety": "；".join(intent.constraints) or "默认本地优先，真实动作前再次确认。",
        "bom": [],
        "ioMap": [],
        "acceptanceScenarios": scenarios,
        "sourceProposalId": spec.id,
    }


def _contains(value: str, *needles: str) -> bool:
    return any(needle.casefold() in value for needle in needles)


def _joined(values: list[str], fallback: str) -> str:
    return "、".join(value for value in values if value).strip() or fallback


def _scene_identity(
    lowered: str,
    intent: WorkIntent,
) -> tuple[WorkSceneKind, str, str]:
    if not any(
        node_need
        for node_need in (
            intent.physical_actions,
            intent.structure_needs,
        )
    ) and _contains(lowered, "软件", "网页", "应用", "software", "web", "app"):
        return WorkSceneKind.GENERIC, "SOFTWARE", intent.title
    if _contains(lowered, "花盆", "植物", "浇花", "浇水", "土壤", "plant", "watering"):
        return WorkSceneKind.PLANT, "PLANTER", "智能花盆"
    if _contains(lowered, "姿态", "坐姿", "提醒", "posture", "remind"):
        return WorkSceneKind.DESK, "REMINDER", "桌面提醒作品"
    if _contains(lowered, "房间", "家居", "门", "room", "home"):
        return WorkSceneKind.ROOM, "MACHINE", "房间里的智能作品"
    if _contains(lowered, "灯", "照明", "light", "led"):
        return WorkSceneKind.DEVICE, "LIGHT", "互动灯光作品"
    if _contains(lowered, "屏幕", "显示", "天气", "display", "weather"):
        return WorkSceneKind.DISPLAY, "DISPLAY", "信息显示作品"
    if intent.physical_actions or _contains(lowered, "电机", "舵机", "运动", "motor", "servo"):
        return WorkSceneKind.MOTION, "MACHINE", "会行动的智能作品"
    return WorkSceneKind.GENERIC, "GENERIC", intent.title


def _scene_environment(intent: WorkIntent) -> WorkSceneEnvironment:
    lowered = " ".join([*intent.environments, intent.summary]).casefold()
    if _contains(lowered, "户外", "室外", "outdoor"):
        return WorkSceneEnvironment(
            kind="OUTDOOR",
            label="户外环境",
            description="作品位于户外，需要考虑天气和安全边界。",
        )
    if _contains(lowered, "桌面", "坐姿", "desk", "desktop"):
        return WorkSceneEnvironment(
            kind="DESKTOP",
            label="桌面场景",
            description="作品和使用者在同一桌面空间中互动。",
        )
    if _contains(lowered, "家庭", "家里", "花盆", "home"):
        return WorkSceneEnvironment(
            kind="HOME",
            label="家庭环境",
            description="作品在家庭空间中持续工作并给出可见结果。",
        )
    if _contains(lowered, "室内", "indoor"):
        return WorkSceneEnvironment(
            kind="INDOOR",
            label="室内环境",
            description="作品在室内环境中运行。",
        )
    if _contains(lowered, "花盆", "植物", "浇花", "浇水", "plant", "watering"):
        return WorkSceneEnvironment(
            kind="GENERIC",
            label="花盆旁",
            description="作品围绕花盆工作，具体摆放在室内还是户外仍可继续补充。",
        )
    return WorkSceneEnvironment(
        kind="GENERIC",
        label="使用场景",
        description="场景细节仍可通过对话继续补充。",
    )


def _scene_part_label(role: str, nodes: list[CanvasNode]) -> str:
    role_labels = {
        "SUBJECT": "作品主体",
        "INPUT": "它会留意",
        "DECISION": "它会判断",
        "ACTION": "它会行动",
        "RESULT": "你会看到",
        "POWER": "安全供电",
        "STRUCTURE": "外形结构",
        "SERVICE": "设备通信",
    }
    titles = "、".join(node.title for node in nodes[:2])
    return f"{role_labels[role]}：{titles}"


def _scene_relation_groups(
    nodes: list[CanvasNode],
    edges: list[CanvasEdge],
) -> dict[str, list[str]]:
    kind_by_id = {node.id: node.kind for node in nodes}
    groups = {"TRIGGER": [], "DECIDE": [], "ACT": [], "RESULT": [], "FAULT": []}
    for edge in edges:
        source = kind_by_id.get(edge.source_node_id)
        target = kind_by_id.get(edge.target_node_id)
        if source is CanvasNodeKind.INPUT or target is CanvasNodeKind.INPUT:
            groups["TRIGGER"].append(edge.id)
        if source is CanvasNodeKind.BEHAVIOR or target is CanvasNodeKind.BEHAVIOR:
            groups["DECIDE"].append(edge.id)
        if target in {CanvasNodeKind.PHYSICAL_ACTION, CanvasNodeKind.POWER}:
            groups["ACT"].append(edge.id)
        if target in {CanvasNodeKind.OUTPUT, CanvasNodeKind.SERVICE}:
            groups["RESULT"].append(edge.id)
        if edge.active_state in {CanvasEdgeActiveState.BLOCKED, CanvasEdgeActiveState.PROPOSED}:
            groups["FAULT"].append(edge.id)
    return groups


def _append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _canvas_source_digest(
    intent: WorkIntent,
    spec: CanvasSpec,
    *,
    seed: object,
) -> str:
    intent_payload = intent.model_dump(by_alias=True, mode="json")
    for volatile_key in ("id", "revision", "createdAt"):
        intent_payload.pop(volatile_key, None)
    scene_payload = (
        spec.scene.model_dump(by_alias=True, mode="json")
        if spec.scene is not None
        else None
    )
    if scene_payload is not None:
        scene_payload.pop("sourceCanvasId", None)
        scene_payload.pop("sourceCanvasRevision", None)
    return _digest(
        {
            "seed": seed,
            "intent": intent_payload,
            "nodes": [
                node.model_dump(by_alias=True, mode="json") for node in spec.nodes
            ],
            "edges": [
                edge.model_dump(by_alias=True, mode="json") for edge in spec.edges
            ],
            "scene": scene_payload,
            "naturalStatus": spec.natural_status,
        }
    )


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _now() -> str:
    return datetime.now(UTC).isoformat()

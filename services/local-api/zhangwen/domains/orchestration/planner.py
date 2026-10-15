"""Deterministic routing policy for the three internal units."""

from __future__ import annotations

from dataclasses import dataclass

from zhangwen.domains.orchestration.models import InternalUnit
from zhangwen.domains.works.models import WorkJourneyMilestone, WorkSnapshot


_DISCOVERY_TERMS = ("想法", "目标", "需求", "场景", "用户", "功能", "为什么", "用途")
_ENGINEERING_TERMS = (
    "代码",
    "程序",
    "硬件",
    "电路",
    "设备",
    "传感器",
    "执行器",
    "供电",
    "仿真",
    "测试",
    "接口",
    "参数",
    "服务",
    "装置",
    "提醒",
    "联网",
    "物联网",
    "网络",
    "远程",
    "mqtt",
)
_STRUCTURE_TERMS = ("结构", "外壳", "尺寸", "装配", "支架", "固定", "cad", "3d", "打印")


@dataclass(frozen=True)
class PlannedInvocation:
    intent: str
    units: list[InternalUnit]


class InvocationPlanner:
    def plan(self, snapshot: WorkSnapshot, message: str) -> PlannedInvocation:
        normalized = message.strip().lower()
        discovery = any(term in normalized for term in _DISCOVERY_TERMS)
        engineering = any(term in normalized for term in _ENGINEERING_TERMS)
        structure = any(term in normalized for term in _STRUCTURE_TERMS)

        # A new work should never jump straight from the user's first sentence
        # into engineering. The discovery unit establishes the visible intent
        # first; engineering and structure still join only when the content
        # calls for them.
        if snapshot.milestone is WorkJourneyMilestone.CLARIFY:
            discovery = True

        units: list[InternalUnit] = []
        if discovery:
            units.append(InternalUnit.DISCOVERY_ROLE)
        if engineering or structure:
            units.append(InternalUnit.ENGINEERING_ROLE)
        if structure:
            units.append(InternalUnit.STRUCTURE_ROLE)
        if not units:
            units.append(
                InternalUnit.ENGINEERING_ROLE
                if snapshot.milestone
                in {
                    WorkJourneyMilestone.TRY,
                    WorkJourneyMilestone.MAKE,
                    WorkJourneyMilestone.COMPLETE,
                }
                else InternalUnit.DISCOVERY_ROLE
            )

        intent = (
            "structure_change"
            if structure
            else "engineering_change"
            if engineering
            else "work_discovery"
        )
        return PlannedInvocation(intent=intent, units=list(dict.fromkeys(units)))

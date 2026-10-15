"""Side-effect-free local boundary for one internal orchestration unit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from zhangwen.domains.orchestration.models import InternalUnit
from zhangwen.domains.works.models import WorkSnapshot


@dataclass(frozen=True)
class UnitExecutionResult:
    summary: str
    response_fragment: str


class UnitExecutor(Protocol):
    async def execute(
        self,
        *,
        unit: InternalUnit,
        message: str,
        snapshot: WorkSnapshot,
    ) -> UnitExecutionResult: ...


class LocalInternalUnitExecutor:
    """Produces validated advisory output without host capabilities or side effects."""

    async def execute(
        self,
        *,
        unit: InternalUnit,
        message: str,
        snapshot: WorkSnapshot,
    ) -> UnitExecutionResult:
        normalized = message.strip().casefold()
        reminder = _contains(normalized, "提醒", "闹钟", "通知", "蜂鸣", "灯光")
        connected = _contains(
            normalized,
            "联网",
            "物联网",
            "网络",
            "远程",
            "mqtt",
            "手机查看",
        )
        if unit is InternalUnit.DISCOVERY_ROLE:
            response = (
                "我先把第一版聚焦为“触发条件 → 可观察结果 → 完成判断”，"
                "并把不确定项压缩到真正会阻塞实现的一件事。"
            )
            if reminder:
                response = (
                    "我先把提醒类作品整理为“触发 → 提醒 → 用户确认或状态记录”，"
                    "第一版会先验证这条最短闭环。"
                )
            if connected:
                response += (
                    " 联网查看会作为受控连接加入；先验证本地核心行为，"
                    "再由你确认只在本机、家庭网络还是已有外部服务中查看。"
                )
            return UnitExecutionResult(
                summary="已从输入中整理作品目标、最短行为闭环和待确认边界。",
                response_fragment=response,
            )
        if unit is InternalUnit.ENGINEERING_ROLE:
            response = (
                "我先把第一版拆成“输入或触发 → 本地判断 → 可观察结果”，"
                "先在数字版本中验证，再决定真实设备。"
            )
            if reminder:
                response = (
                    "我先把第一版拆成“触发 → 提醒 → 确认或状态记录”，"
                    "先验证提醒不会漏发或反复打扰。"
                )
            if connected:
                response += (
                    " 联网查看单独作为受控的一层，默认不开放网络；"
                    "本地行为通过后再确认查看范围和连接方式。"
                )
            return UnitExecutionResult(
                summary="已整理第一版数字行为、设备顺序和联网安全边界。",
                response_fragment=response,
            )
        return UnitExecutionResult(
            summary="已安排按需结构、装配和制造约束检查。",
            response_fragment=(
                f"结构部分会围绕“{snapshot.work.name}”的使用位置、固定方式和装配空间按需展开，"
                "不会在行为方案明确前先假定外壳。"
            ),
        )


def _contains(value: str, *terms: str) -> bool:
    return any(term in value for term in terms)

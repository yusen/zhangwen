"""Validated V2 navigation context shared by project chat and expert runtime."""

from __future__ import annotations

from typing import Any


def v2_workspace_prompt_context(turn_context: dict | None) -> str | None:
    """Return a bounded prompt hint; page state never grants execution authority."""

    if not isinstance(turn_context, dict):
        return None
    workspace_kind = turn_context.get("workspaceKind")
    workspace_view = turn_context.get("workspaceView")
    if not isinstance(workspace_kind, str) or not isinstance(workspace_view, str):
        return None
    labels: dict[str, tuple[str, dict[str, str]]] = {
        "overview": ("项目概览", {"overview": "目标与方案"}),
        "engineering": (
            "工程实现",
            {
                "hardware": "硬件与供电",
                "code": "代码工程",
                "device": "设备运行态",
                "validation": "验证证据",
            },
        ),
        "structure": ("结构设计", {"cad": "3D 结构与修订"}),
        "delivery": ("成果交付", {"release": "版本、产物与发布准备"}),
    }
    definition = labels.get(workspace_kind)
    if definition is None or workspace_view not in definition[1]:
        return None
    version = turn_context.get("projectVersion")
    version_label = (
        f"，项目版本 V{version}"
        if isinstance(version, int) and 0 <= version <= 1_000_000
        else ""
    )
    return (
        f"当前 V2 页面上下文：{definition[0]} / {definition[1][workspace_view]}{version_label}。"
        "请优先回答当前页面相关问题，并引用项目中的已确认事实和实际产物；"
        "页面上下文只是导航提示，不代表本地工具已经执行、设备已经写入或结果已经验证。"
    )


def bounded_v2_workspace_context(turn_context: dict | None) -> dict[str, Any] | None:
    """Keep only display-routing fields before crossing into Expert Runtime."""

    if v2_workspace_prompt_context(turn_context) is None:
        return None
    assert isinstance(turn_context, dict)
    result: dict[str, Any] = {
        "workspaceKind": turn_context["workspaceKind"],
        "workspaceView": turn_context["workspaceView"],
    }
    version = turn_context.get("projectVersion")
    if isinstance(version, int) and 0 <= version <= 1_000_000:
        result["projectVersion"] = version
    return result

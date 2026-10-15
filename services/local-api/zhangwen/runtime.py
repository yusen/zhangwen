"""掌问本地服务 — 运行时状态"""

import time

_start_time: float = time.monotonic()


def get_uptime_seconds() -> float:
    """返回服务运行时长（秒）"""
    return time.monotonic() - _start_time


def reset_start_time() -> None:
    """重置启动时间（用于测试或重启场景）"""
    global _start_time
    _start_time = time.monotonic()

"""Isolated restricted-CPython behavioral reference for the ZW worker protocol.

This worker is deliberately labelled as a reference implementation. It cannot produce
native-MicroPython or project Evidence and is never an implicit fallback for native mode.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
import tracemalloc
from pathlib import Path
from types import ModuleType
from typing import Any


if getattr(sys, "frozen", False):
    from zhangwen.domains.simulation.runtime import component_bus as _BUS_MODULE
else:
    _BUS_PATH = Path(__file__).with_name("component_bus.py").resolve()
    _BUS_SPEC = importlib.util.spec_from_file_location(
        "_zhangwen_component_bus", _BUS_PATH
    )
    if _BUS_SPEC is None or _BUS_SPEC.loader is None:
        raise RuntimeError("fixed component bus module is unavailable")
    _BUS_MODULE = importlib.util.module_from_spec(_BUS_SPEC)
    sys.modules[_BUS_SPEC.name] = _BUS_MODULE
    _BUS_SPEC.loader.exec_module(_BUS_MODULE)
ComponentBus = _BUS_MODULE.ComponentBus
ReadOnlyBundleFile = _BUS_MODULE.ReadOnlyBundleFile
ResourceLimitExceeded = _BUS_MODULE.ResourceLimitExceeded
SimulationRuntimeFault = _BUS_MODULE.SimulationRuntimeFault
UnsupportedSimulationFeature = _BUS_MODULE.UnsupportedSimulationFeature
build_modules = _BUS_MODULE.build_modules


PROTOCOL = "zhangwen.micropython-worker/v1"
MAX_REQUEST_BYTES = 2_000_000
MAX_RESPONSE_BYTES = 2_000_000
_BUNDLE_FILENAME_PREFIX = "<bundle:"


class SourcePolicyError(SimulationRuntimeFault):
    def __init__(self, message: str) -> None:
        super().__init__("SIMULATION_SOURCE_POLICY_REJECTED", message)


class SourcePolicy(ast.NodeVisitor):
    _DENIED = (
        ast.ClassDef,
        ast.AsyncFunctionDef,
        ast.Await,
        ast.AsyncFor,
        ast.AsyncWith,
        ast.Try,
        ast.Raise,
        ast.Global,
        ast.Nonlocal,
        ast.Delete,
        ast.Yield,
        ast.YieldFrom,
        ast.NamedExpr,
    )
    _ALLOWED_IMPORTS = {"machine", "time", "dht", "ssd1306", "neopixel", "random"}
    _BANNED_NAMES = {
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "getattr",
        "globals",
        "help",
        "input",
        "locals",
        "setattr",
        "type",
        "vars",
    }

    def __init__(self, user_modules: set[str]) -> None:
        self.user_modules = user_modules

    def generic_visit(self, node: ast.AST) -> Any:
        if isinstance(node, self._DENIED):
            raise SourcePolicyError(
                f"当前行为参考 Worker 不允许语法 {node.__class__.__name__}。"
            )
        return super().generic_visit(node)

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id.startswith("_") or node.id in self._BANNED_NAMES:
            raise SourcePolicyError(f"代码使用了受限名称 {node.id}。")
        return self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if node.attr.startswith("_"):
            raise SourcePolicyError(f"代码使用了受限属性 {node.attr}。")
        return self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            if alias.name not in self._ALLOWED_IMPORTS | self.user_modules:
                raise UnsupportedSimulationFeature(f"import {alias.name}")
            if alias.asname is not None and alias.asname.startswith("_"):
                raise SourcePolicyError("导入别名不能以下划线开头。")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if node.level != 0 or node.module is None:
            raise SourcePolicyError("行为参考 Worker 不支持相对导入。")
        if node.module not in self._ALLOWED_IMPORTS | self.user_modules:
            raise UnsupportedSimulationFeature(f"import {node.module}")
        for alias in node.names:
            if alias.name == "*" or alias.name.startswith("_"):
                raise SourcePolicyError("行为参考 Worker 不支持星号或私有名称导入。")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        if node.name.startswith("_") or node.decorator_list:
            raise SourcePolicyError("函数名不能为私有名称，且不支持装饰器。")
        return self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> Any:
        value = node.value
        if isinstance(value, (str, bytes)) and len(value) > 100_000:
            raise SourcePolicyError("单个代码常量超过行为参考 Worker 上限。")
        if isinstance(value, int) and value.bit_length() > 4096:
            raise SourcePolicyError("整数常量超过行为参考 Worker 上限。")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        if isinstance(node.op, ast.Pow):
            if not isinstance(node.right, ast.Constant) or not isinstance(
                node.right.value, int
            ):
                raise SourcePolicyError("幂运算指数必须是受限整数常量。")
            if abs(node.right.value) > 4096:
                raise SourcePolicyError("幂运算指数超过行为参考 Worker 上限。")
        return self.generic_visit(node)


class InstructionBudget:
    def __init__(self, maximum: int, max_heap_bytes: int) -> None:
        self.maximum = maximum
        self.max_heap_bytes = max_heap_bytes
        self.instructions = 0
        self.peak_heap_bytes = 0

    def trace(self, frame: Any, event: str, arg: Any) -> Any:
        del arg
        if event == "call" and str(frame.f_code.co_filename).startswith(
            _BUNDLE_FILENAME_PREFIX
        ):
            frame.f_trace_opcodes = True
            return self.trace
        if not str(frame.f_code.co_filename).startswith(_BUNDLE_FILENAME_PREFIX):
            return None
        if event in {"opcode", "line"}:
            self.instructions += 1
            if self.instructions > self.maximum:
                raise ResourceLimitExceeded(
                    "SIMULATION_INSTRUCTION_LIMIT_EXCEEDED",
                    "代码执行步数超过当前运行上限。",
                )
            if self.instructions % 64 == 0:
                _current, peak = tracemalloc.get_traced_memory()
                self.peak_heap_bytes = max(self.peak_heap_bytes, peak)
                if peak > self.max_heap_bytes:
                    raise ResourceLimitExceeded(
                        "SIMULATION_HEAP_LIMIT_EXCEEDED",
                        "代码堆内存超过当前运行上限。",
                    )
        return self.trace


class BundleExecutor:
    def __init__(
        self,
        *,
        files: dict[str, str],
        modules: dict[str, ModuleType],
        bus: ComponentBus,
        budget: InstructionBudget,
    ) -> None:
        self.files = files
        self.modules = modules
        self.bus = bus
        self.budget = budget
        self.user_module_paths = {
            path.removesuffix(".py").replace("/", "."): path
            for path in files
            if path.endswith(".py") and path != "main.py"
        }
        self.loaded_user_modules: dict[str, ModuleType] = {}

    def execute(self) -> None:
        self._execute_source(
            self.files["main.py"],
            "main.py",
            self._globals("__main__"),
        )

    def _globals(self, module_name: str) -> dict[str, Any]:
        safe_builtins: dict[str, Any] = {
            "__import__": self._import,
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "bytes": bytes,
            "bytearray": bytearray,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "int": int,
            "isinstance": isinstance,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "print": self.bus.collector.serial_write,
            "range": range,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
            "open": self._open,
        }
        return {
            "__builtins__": safe_builtins,
            "__name__": module_name,
            "__package__": None,
        }

    def _execute_source(
        self, source: str, path: str, namespace: dict[str, Any]
    ) -> None:
        try:
            tree = ast.parse(source, filename=f"{_BUNDLE_FILENAME_PREFIX}{path}>")
        except SyntaxError as exc:
            location = f"第 {exc.lineno} 行" if exc.lineno else "未知位置"
            raise SimulationRuntimeFault(
                "MICROPYTHON_SYNTAX_ERROR",
                f"MicroPython 源码语法错误（{location}）。",
            ) from exc
        SourcePolicy(set(self.modules) | set(self.user_module_paths)).visit(tree)
        code = compile(tree, f"{_BUNDLE_FILENAME_PREFIX}{path}>", "exec")
        exec(code, namespace, namespace)

    def _import(
        self,
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] | list[str] = (),
        level: int = 0,
    ) -> ModuleType:
        del globals, locals
        if level != 0:
            raise SourcePolicyError("行为参考 Worker 不支持相对导入。")
        if name in self.modules:
            return self.modules[name]
        if name not in self.user_module_paths:
            raise UnsupportedSimulationFeature(f"import {name}")
        if name not in self.loaded_user_modules:
            module = ModuleType(name)
            namespace = self._globals(name)
            module.__dict__.update(namespace)
            self.loaded_user_modules[name] = module
            self._execute_source(
                self.files[self.user_module_paths[name]],
                self.user_module_paths[name],
                module.__dict__,
            )
        del fromlist
        return self.loaded_user_modules[name]

    def _open(
        self,
        path: str,
        mode: str = "r",
        *_args: Any,
        **_kwargs: Any,
    ) -> ReadOnlyBundleFile:
        normalized = str(path).replace("\\", "/")
        if (
            normalized.startswith("/")
            or ":" in normalized
            or any(part in {"", ".", ".."} for part in normalized.split("/"))
        ):
            raise SourcePolicyError("文件路径必须是 CodeBundle 内的规范相对路径。")
        if mode not in {"r", "rb", "rt", "br", "tr"}:
            raise UnsupportedSimulationFeature("host filesystem writes")
        if normalized not in self.files:
            raise SimulationRuntimeFault(
                "SIMULATION_BUNDLE_FILE_NOT_FOUND",
                f"CodeBundle 中不存在文件 {normalized}。",
            )
        return ReadOnlyBundleFile(self.files[normalized], binary="b" in mode)


def _empty_result(
    engine_mode: str,
    status: str,
    *,
    error: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema": "zhangwen.simulation-runtime-result/v1",
        "engineMode": engine_mode,
        "status": status,
        "runtimePackageRevisionId": "runtime/zw-mpy-sim@1",
        "nativeCoreVerified": False,
        "evidenceEligible": False,
        "deterministicDigest": None,
        "serialOutput": "",
        "events": [],
        "resourceUsage": {
            "instructions": 0,
            "events": 0,
            "outputBytes": 0,
            "peakHeapBytes": 0,
            "virtualTimeUs": 0,
        },
        "error": error,
    }


def execute(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("protocol") != PROTOCOL:
        return _empty_result(
            "BEHAVIORAL_REFERENCE",
            "FAILED",
            error={
                "code": "SIMULATION_WORKER_PROTOCOL_MISMATCH",
                "message": "仿真 Worker 协议不匹配。",
                "retryable": False,
            },
        )
    request = payload.get("request")
    board_profile = payload.get("boardProfile")
    component_profiles = payload.get("componentProfiles")
    if not isinstance(request, dict) or not isinstance(board_profile, dict) or not isinstance(
        component_profiles, list
    ):
        return _empty_result(
            "BEHAVIORAL_REFERENCE",
            "FAILED",
            error={
                "code": "SIMULATION_WORKER_INPUT_INVALID",
                "message": "仿真 Worker 输入未通过结构边界。",
                "retryable": False,
            },
        )
    limits = request["limits"]
    files = {
        str(item["path"]): str(item["content"])
        for item in request["codeBundle"]["files"]
    }
    bus: ComponentBus | None = None
    budget = InstructionBudget(
        int(limits["maxInstructions"]), int(limits["maxHeapBytes"])
    )
    tracemalloc.start()
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(min(old_limit, 200))
    try:
        bus = ComponentBus(
            board_profile=board_profile,
            component_profiles=component_profiles,
            circuit=request["circuit"],
            seed=int(request["seed"]),
            uart_inputs=dict(request.get("uartInputs", {})),
            scenario_actions=list(request.get("scenarioActions", [])),
            max_events=int(limits["maxEvents"]),
            max_output_bytes=int(limits["maxOutputBytes"]),
            max_virtual_time_us=int(limits["maxVirtualTimeUs"]),
        )
        executor = BundleExecutor(
            files=files,
            modules=build_modules(bus),
            bus=bus,
            budget=budget,
        )
        sys.settrace(budget.trace)
        executor.execute()
        sys.settrace(None)
        _current, peak = tracemalloc.get_traced_memory()
        budget.peak_heap_bytes = max(budget.peak_heap_bytes, peak)
        if peak > budget.max_heap_bytes:
            raise ResourceLimitExceeded(
                "SIMULATION_HEAP_LIMIT_EXCEEDED",
                "代码堆内存超过当前运行上限。",
            )
        semantic = {
            "events": bus.collector.events,
            "serialOutput": bus.collector.serial_output,
            "virtualTimeUs": bus.clock.now_us,
            "seed": int(request["seed"]),
        }
        digest = hashlib.sha256(
            json.dumps(
                semantic,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return {
            "schema": "zhangwen.simulation-runtime-result/v1",
            "engineMode": "BEHAVIORAL_REFERENCE",
            "status": "COMPLETED",
            "runtimePackageRevisionId": "runtime/zw-mpy-sim@1",
            "nativeCoreVerified": False,
            "evidenceEligible": False,
            "deterministicDigest": digest,
            "serialOutput": bus.collector.serial_output,
            "events": bus.collector.events,
            "resourceUsage": {
                "instructions": budget.instructions,
                "events": len(bus.collector.events),
                "outputBytes": bus.collector.output_bytes,
                "peakHeapBytes": budget.peak_heap_bytes,
                "virtualTimeUs": bus.clock.now_us,
            },
            "error": None,
        }
    except SimulationRuntimeFault as exc:
        sys.settrace(None)
        collector = bus.collector if bus is not None else None
        clock = bus.clock if bus is not None else None
        _current, peak = tracemalloc.get_traced_memory()
        return {
            **_empty_result(
                "BEHAVIORAL_REFERENCE",
                "FAILED",
                error={"code": exc.code, "message": exc.message, "retryable": False},
            ),
            "serialOutput": collector.serial_output if collector is not None else "",
            "events": collector.events if collector is not None else [],
            "resourceUsage": {
                "instructions": budget.instructions,
                "events": len(collector.events) if collector is not None else 0,
                "outputBytes": collector.output_bytes if collector is not None else 0,
                "peakHeapBytes": max(budget.peak_heap_bytes, peak),
                "virtualTimeUs": clock.now_us if clock is not None else 0,
            },
        }
    except BaseException as exc:
        sys.settrace(None)
        collector = bus.collector if bus is not None else None
        clock = bus.clock if bus is not None else None
        _current, peak = tracemalloc.get_traced_memory()
        return {
            **_empty_result(
                "BEHAVIORAL_REFERENCE",
                "FAILED",
                error={
                    "code": "MICROPYTHON_RUNTIME_ERROR",
                    "message": f"行为参考执行失败：{exc.__class__.__name__}: {str(exc)[:400]}",
                    "retryable": False,
                },
            ),
            "serialOutput": collector.serial_output if collector is not None else "",
            "events": collector.events if collector is not None else [],
            "resourceUsage": {
                "instructions": budget.instructions,
                "events": len(collector.events) if collector is not None else 0,
                "outputBytes": collector.output_bytes if collector is not None else 0,
                "peakHeapBytes": max(budget.peak_heap_bytes, peak),
                "virtualTimeUs": clock.now_us if clock is not None else 0,
            },
        }
    finally:
        sys.settrace(None)
        sys.setrecursionlimit(old_limit)
        tracemalloc.stop()


def main() -> int:
    encoded = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(encoded) > MAX_REQUEST_BYTES:
        response = _empty_result(
            "BEHAVIORAL_REFERENCE",
            "FAILED",
            error={
                "code": "SIMULATION_WORKER_INPUT_LIMIT_EXCEEDED",
                "message": "仿真 Worker 输入超过上限。",
                "retryable": False,
            },
        )
    else:
        try:
            payload = json.loads(encoded.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError
            response = execute(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            response = _empty_result(
                "BEHAVIORAL_REFERENCE",
                "FAILED",
                error={
                    "code": "SIMULATION_WORKER_INPUT_INVALID",
                    "message": "仿真 Worker 输入不是有效 JSON。",
                    "retryable": False,
                },
            )
    output = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
    if len(output.encode("utf-8")) > MAX_RESPONSE_BYTES:
        output = json.dumps(
            _empty_result(
                "BEHAVIORAL_REFERENCE",
                "FAILED",
                error={
                    "code": "SIMULATION_WORKER_OUTPUT_LIMIT_EXCEEDED",
                    "message": "仿真 Worker 结果超过协议上限。",
                    "retryable": False,
                },
            ),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

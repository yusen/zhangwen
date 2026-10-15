"""Fixed-argv process supervision for the independent local MQTT broker."""

from __future__ import annotations

import hashlib
import os
import signal
import socket
import ssl
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from zhangwen.cad_agent.process_limits import WindowsJobObject
from zhangwen.config import settings
from zhangwen.domains.mqtt_service.models import (
    MqttMode,
    MqttServiceConflictError,
    MqttServiceInstance,
    MqttServiceUnavailableError,
)


class BrokerProcess(Protocol):
    @property
    def pid(self) -> int: ...

    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def error_summary(self) -> str | None: ...

    def close_limits(self) -> None: ...


class BrokerProcessAdapter(Protocol):
    def start(self, config_path: Path, instance: MqttServiceInstance) -> BrokerProcess: ...

    def healthy(self, process: BrokerProcess, instance: MqttServiceInstance) -> bool: ...


class ExternalServiceProbe(Protocol):
    def healthy(self, instance: MqttServiceInstance) -> bool: ...


@dataclass(frozen=True)
class BrokerCrash:
    instance_id: str
    exit_code: int
    error_summary: str | None


@dataclass
class BrokerRuntime:
    process: BrokerProcess
    config_digest: str
    active_instance_ids: set[str]


class ManagedBrokerProcess:
    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process
        self._stderr: deque[str] = deque(maxlen=32)
        self._limits = WindowsJobObject(
            process.pid,
            memory_bytes=256 * 1024 * 1024,
            cpu_seconds=24 * 60 * 60,
        )
        for stream, target in (
            (process.stdout, deque(maxlen=32)),
            (process.stderr, self._stderr),
        ):
            if stream is not None:
                threading.Thread(
                    target=_drain_stream,
                    args=(stream, target),
                    daemon=True,
                    name=f"mqtt-broker-log-{process.pid}",
                ).start()

    @property
    def pid(self) -> int:
        return self._process.pid

    def poll(self) -> int | None:
        return self._process.poll()

    def terminate(self) -> None:
        self._process.terminate()

    def kill(self) -> None:
        _terminate_process_tree(self._process)

    def wait(self, timeout: float | None = None) -> int:
        return self._process.wait(timeout=timeout)

    def error_summary(self) -> str | None:
        value = " | ".join(self._stderr)
        return _sanitize_log(value) if value else None

    def close_limits(self) -> None:
        self._limits.close()


class SubprocessBrokerAdapter:
    """Production adapter; executable and digest come only from local packaging."""

    def start(self, config_path: Path, instance: MqttServiceInstance) -> BrokerProcess:
        executable = settings.mqtt_broker_executable
        expected_digest = settings.mqtt_broker_sha256
        if executable is None or not executable.is_file() or not expected_digest:
            raise MqttServiceUnavailableError(
                "本机设备通信运行组件尚未安装；没有启动任何进程。"
            )
        actual_digest = hashlib.sha256(executable.read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            raise MqttServiceUnavailableError(
                "本机设备通信运行组件校验失败；没有启动任何进程。"
            )
        creationflags = 0
        start_new_session = os.name != "nt"
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        process = subprocess.Popen(
            [str(executable), "--config", str(config_path)],
            cwd=str(config_path.parent),
            env=_minimal_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            creationflags=creationflags,
            start_new_session=start_new_session,
        )
        try:
            return ManagedBrokerProcess(process)
        except Exception:
            _terminate_process_tree(process)
            raise

    def healthy(self, process: BrokerProcess, instance: MqttServiceInstance) -> bool:
        if process.poll() is not None or instance.listen_host is None or instance.listen_port is None:
            return False
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                return False
            try:
                with socket.create_connection(
                    (instance.listen_host, instance.listen_port),
                    timeout=0.2,
                ):
                    return True
            except OSError:
                time.sleep(0.05)
        return False


class TlsExternalServiceProbe:
    def healthy(self, instance: MqttServiceInstance) -> bool:
        endpoint = instance.external_endpoint
        if not endpoint:
            return False
        host, port = _split_endpoint(endpoint)
        context = ssl.create_default_context()
        try:
            with socket.create_connection((host, port), timeout=3.0) as raw:
                with context.wrap_socket(raw, server_hostname=host):
                    return True
        except OSError:
            return False


class MqttBrokerSupervisor:
    def __init__(
        self,
        data_dir: Path,
        *,
        adapter: BrokerProcessAdapter | None = None,
        external_probe: ExternalServiceProbe | None = None,
    ) -> None:
        self.data_dir = Path(data_dir).resolve()
        self._adapter = adapter or SubprocessBrokerAdapter()
        self._external_probe = external_probe or TlsExternalServiceProbe()
        self._runtime: BrokerRuntime | None = None
        self._pending_crashes: dict[str, BrokerCrash] = {}
        self._lock = threading.RLock()

    @property
    def local_process_running(self) -> bool:
        with self._lock:
            return self._runtime is not None and self._runtime.process.poll() is None

    def start(
        self,
        instance: MqttServiceInstance,
        config: str,
        *,
        config_digest: str | None = None,
    ) -> int | None:
        if instance.mode is MqttMode.SIMULATED:
            return None
        if instance.mode is MqttMode.EXTERNAL:
            if not self._external_probe.healthy(instance):
                raise MqttServiceUnavailableError(
                    "已有通信服务没有通过 TLS 健康检查；未降级到明文连接。"
                )
            return None
        with self._lock:
            expected_digest = config_digest or instance.config_digest
            if self._runtime is not None:
                process = self._runtime.process
                if process.poll() is None:
                    if self._runtime.config_digest != expected_digest:
                        raise MqttServiceConflictError(
                            "本机通信配置集合已经固定；请安全停止全部本地通信后再载入新配置。"
                        )
                    if not self._adapter.healthy(process, instance):
                        raise MqttServiceUnavailableError(
                            "共享本机通信进程没有通过当前作品的受限监听探测。"
                        )
                    self._runtime.active_instance_ids.add(instance.id)
                    return process.pid
                exit_code = process.poll()
                summary = process.error_summary()
                self._pending_crashes.update(
                    {
                        affected_id: BrokerCrash(
                            affected_id,
                            int(exit_code if exit_code is not None else -1),
                            summary,
                        )
                        for affected_id in self._runtime.active_instance_ids
                    }
                )
                self._release_process(process)
                self._runtime = None
            config_path = self._materialize_config(
                instance,
                config,
                expected_digest=expected_digest,
            )
            process = self._adapter.start(config_path, instance)
            if not self._adapter.healthy(process, instance):
                error = process.error_summary()
                self._bounded_stop(process)
                raise MqttServiceUnavailableError(
                    error or "本机通信进程没有通过进程、监听地址和协议探测。"
                )
            self._runtime = BrokerRuntime(
                process=process,
                config_digest=expected_digest,
                active_instance_ids={instance.id},
            )
            return process.pid

    def stop(self, instance_id: str) -> None:
        with self._lock:
            if self._runtime is None or instance_id not in self._runtime.active_instance_ids:
                return
            self._runtime.active_instance_ids.remove(instance_id)
            if self._runtime.active_instance_ids:
                return
            process = self._runtime.process
            self._runtime = None
            self._bounded_stop(process)

    def poll_crash(self, instance_id: str) -> BrokerCrash | None:
        with self._lock:
            pending = self._pending_crashes.pop(instance_id, None)
            if pending is not None:
                return pending
            if self._runtime is None or instance_id not in self._runtime.active_instance_ids:
                return None
            process = self._runtime.process
            exit_code = process.poll()
            if exit_code is None:
                return None
            affected = set(self._runtime.active_instance_ids)
            self._runtime = None
            summary = process.error_summary()
            self._release_process(process)
            self._pending_crashes.update(
                {
                    affected_id: BrokerCrash(affected_id, exit_code, summary)
                    for affected_id in affected
                }
            )
            return self._pending_crashes.pop(instance_id, None)

    def shutdown(self) -> None:
        with self._lock:
            runtime = self._runtime
            self._runtime = None
            self._pending_crashes.clear()
        if runtime is not None:
            self._bounded_stop(runtime.process)

    def _materialize_config(
        self,
        instance: MqttServiceInstance,
        config: str,
        *,
        expected_digest: str,
    ) -> Path:
        root = (self.data_dir / "services" / "mqtt" / "configs").resolve()
        if self.data_dir not in root.parents:
            raise MqttServiceUnavailableError("本机服务配置目录越界。")
        root.mkdir(parents=True, exist_ok=True)
        target = (root / f"{expected_digest}.json").resolve()
        if root not in target.parents:
            raise MqttServiceUnavailableError("本机服务配置文件越界。")
        encoded = config.encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != expected_digest:
            raise MqttServiceUnavailableError("本机服务配置版本校验失败。")
        if target.exists():
            if target.read_bytes() != encoded:
                raise MqttServiceUnavailableError("本机服务配置摘要发生冲突。")
            return target
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(target)
        return target

    @staticmethod
    def _bounded_stop(process: BrokerProcess) -> None:
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=3.0)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
                try:
                    process.wait(timeout=2.0)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        process.close_limits()

    @staticmethod
    def _release_process(process: BrokerProcess) -> None:
        process.close_limits()


def _minimal_environment() -> dict[str, str]:
    environment: dict[str, str] = {}
    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
        value = os.environ.get(key)
        if value:
            environment[key] = value
    return environment


def _drain_stream(stream: object, target: deque[str]) -> None:
    try:
        for raw_line in stream:  # type: ignore[union-attr]
            target.append(_sanitize_log(str(raw_line)))
    except (OSError, ValueError):
        return


def _sanitize_log(value: str) -> str:
    return value.replace("\r", " ").replace("\n", " ")[:512]


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            timeout=3,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _split_endpoint(endpoint: str) -> tuple[str, int]:
    normalized = endpoint.removeprefix("mqtts://")
    host, separator, port_text = normalized.rpartition(":")
    if not separator or not host:
        raise MqttServiceUnavailableError("已有通信服务地址必须包含主机和端口。")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise MqttServiceUnavailableError("已有通信服务端口无效。") from exc
    if not 1 <= port <= 65535:
        raise MqttServiceUnavailableError("已有通信服务端口无效。")
    return host.strip("[]"), port

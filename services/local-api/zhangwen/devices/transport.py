"""Controlled device transports.

The device service depends on this small protocol instead of importing serial
or subprocess details into the HTTP layer.  Tests use ``MockDeviceTransport``;
the real adapter is deliberately explicit and only builds fixed argv lists.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import sys
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Protocol

from zhangwen.devices.models import DevicePort
from zhangwen.devices.serial_discovery import SerialDiscoveryError, list_serial_ports
from zhangwen.devices.simulator import get_mock_port, list_mock_ports


MAX_COMMAND_OUTPUT = 64_000
DEFAULT_COMMAND_TIMEOUT = 30.0
_IDENTITY_PROBE_SCRIPT = "\n".join(
    [
        "import sys",
        "try:",
        " import os",
        " _uname=os.uname()",
        " _machine=str(getattr(_uname,'machine',''))",
        " _release=str(getattr(_uname,'release',''))",
        "except Exception:",
        " _machine=''",
        " _release=''",
        "print('__ZW_IDENTITY_V1__')",
        "print('implementation='+str(getattr(sys.implementation,'name','')))",
        "print('platform='+str(getattr(sys,'platform','')))",
        "print('machine='+_machine)",
        "print('firmware='+_release)",
        "print('__ZW_IDENTITY_END__')",
    ]
)


class DeviceTransportError(RuntimeError):
    """A bounded transport failure with a user-facing stable error code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.retryable = retryable


class DeviceTransportCanceled(DeviceTransportError):
    def __init__(self, message: str = "设备操作已取消。", *, exit_code: int | None = None) -> None:
        super().__init__("DEVICE_OPERATION_CANCELED", message, exit_code=exit_code)


class DeviceTransportTimedOut(DeviceTransportError):
    def __init__(self, message: str = "设备操作超时。", *, exit_code: int | None = None) -> None:
        super().__init__("DEVICE_OPERATION_TIMEOUT", message, exit_code=exit_code, retryable=True)


@dataclass(frozen=True)
class TransportSession:
    id: str
    port: DevicePort


@dataclass(frozen=True)
class DeviceIdentity:
    """Sanitized runtime identity returned by a non-mutating board probe."""

    implementation: str = ""
    platform: str = ""
    machine: str = ""
    firmware_version: str = ""
    unique_id_hash: str = ""
    modules: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: object) -> "DeviceIdentity":
        if not isinstance(value, dict):
            return cls()
        modules = value.get("modules")
        capabilities = value.get("capabilities")
        return cls(
            implementation=str(value.get("implementation", "")),
            platform=str(value.get("platform", "")),
            machine=str(value.get("machine", "")),
            firmware_version=str(value.get("firmwareVersion", "")),
            unique_id_hash=str(value.get("uniqueIdHash", "")),
            modules=tuple(str(item) for item in modules)
            if isinstance(modules, list)
            else (),
            capabilities=tuple(str(item) for item in capabilities)
            if isinstance(capabilities, list)
            else (),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "implementation": self.implementation,
            "platform": self.platform,
            "machine": self.machine,
            "firmwareVersion": self.firmware_version,
            "uniqueIdHash": self.unique_id_hash,
            "modules": list(self.modules),
            "capabilities": list(self.capabilities),
        }


@dataclass(frozen=True)
class DeviceIdentityRequirement:
    implementation: str
    platform_contains: str
    required_modules: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    machine_contains: str = ""

    def matches(self, identity: DeviceIdentity) -> bool:
        if identity.implementation.casefold() != self.implementation.casefold():
            return False
        if self.platform_contains.casefold() not in identity.platform.casefold():
            return False
        if self.machine_contains and (
            self.machine_contains.casefold() not in identity.machine.casefold()
        ):
            return False
        return (
            set(self.required_modules).issubset(identity.modules)
            and set(self.required_capabilities).issubset(identity.capabilities)
        )


@dataclass
class TransportResult:
    """A command result.  ``exit_code`` is the sole execution outcome source."""

    exit_code: int | None
    output: str = ""
    data: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class DeviceTransport(Protocol):
    async def scan_ports(self) -> list[DevicePort]: ...

    def resolve_port(self, port_id: str) -> DevicePort: ...

    async def connect(
        self,
        port: DevicePort,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[TransportSession, TransportResult]: ...

    async def probe_identity(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[DeviceIdentity, TransportResult]: ...

    async def disconnect(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult: ...

    async def backup_files(
        self,
        session: TransportSession,
        paths: list[str],
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[TransportResult, dict[str, bytes]]: ...

    async def upload_files(
        self,
        session: TransportSession,
        files: dict[str, bytes],
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult: ...

    async def delete_files(
        self,
        session: TransportSession,
        paths: list[str],
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult: ...

    async def read_file(
        self,
        session: TransportSession,
        path: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[TransportResult, bytes | None]: ...

    async def interrupt_runtime(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult: ...

    async def start_runtime(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult: ...

    async def hard_reset(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult: ...

    async def monitor_terminal(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        on_output: Callable[[str], None],
    ) -> TransportResult: ...

    async def write_terminal(
        self,
        session: TransportSession,
        data: bytes,
    ) -> TransportResult: ...

    async def backup_flash_region(
        self,
        session: TransportSession,
        *,
        address: int,
        size: int,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[TransportResult, bytes | None]: ...

    async def inspect_firmware(
        self,
        path: Path,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult: ...

    async def flash_firmware(
        self,
        session: TransportSession,
        path: Path,
        *,
        address: int,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult: ...

    async def verify_firmware(
        self,
        session: TransportSession,
        path: Path,
        *,
        address: int,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult: ...


class MockDeviceTransport:
    """Deterministic in-memory transport for all automated device tests."""

    transport_mode = "MOCK"
    evidence_eligible = False

    def __init__(
        self,
        *,
        ports: list[DevicePort] | None = None,
        files: dict[str, dict[str, bytes]] | None = None,
        failures: dict[str, int] | None = None,
        delays: dict[str, float] | None = None,
        terminal_chunks: dict[str, list[str]] | None = None,
    ) -> None:
        self.ports = list(ports or list_mock_ports())
        self.files: dict[str, dict[str, bytes]] = {
            key: dict(value) for key, value in (files or {}).items()
        }
        self.firmware: dict[str, bytes] = {}
        self.failures = dict(failures or {})
        self.delays = dict(delays or {})
        self.terminal_chunks = {
            key: list(value) for key, value in (terminal_chunks or {}).items()
        }
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self._sessions: dict[str, TransportSession] = {}
        self.identities: dict[str, DeviceIdentity] = {
            port.id: DeviceIdentity(
                implementation="micropython",
                platform="esp32",
                machine=port.chip,
                firmware_version="mock-firmware",
                unique_id_hash=hashlib.sha256(
                    f"mock:{port.id}".encode("utf-8")
                ).hexdigest(),
                modules=("unihiker_k10", "k10_base")
                if "ESP32-S3" in port.chip.upper()
                else (),
                capabilities=("screen", "button", "rgb")
                if "ESP32-S3" in port.chip.upper()
                else (),
            )
            for port in self.ports
        }

    def resolve_port(self, port_id: str) -> DevicePort:
        for port in self.ports:
            if port.id == port_id:
                return port
        # Keep the legacy mock API useful even when a test only supplies a raw
        # mock identifier and did not call scan first.
        return get_mock_port(port_id)

    async def scan_ports(self) -> list[DevicePort]:
        self.calls.append(("scan", ()))
        await self._before("scan", asyncio.Event())
        return [port.model_copy(deep=True) for port in self.ports]

    async def connect(
        self,
        port: DevicePort,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[TransportSession, TransportResult]:
        self.calls.append(("connect", (port.id,)))
        await self._before("connect", cancel)
        if not any(item.id == port.id for item in self.ports):
            return (
                TransportSession("", port),
                TransportResult(2, "port not found"),
            )
        result = self._result("connect")
        if result.exit_code != 0:
            return TransportSession("mock-failed-session", port), result
        session = TransportSession(f"mock-session-{uuid.uuid4().hex}", port)
        self._sessions[session.id] = session
        self.files.setdefault(port.id, {})
        result.output = "mock serial attachment established; identity not probed"
        return session, result

    async def probe_identity(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[DeviceIdentity, TransportResult]:
        self.calls.append(("identity", (session.port.id,)))
        await self._before("identity", cancel)
        identity = self.identities.get(session.port.id, DeviceIdentity())
        result = self._result("identity")
        result.data["identity"] = identity.as_dict()
        return identity, result

    async def disconnect(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        self.calls.append(("disconnect", (session.port.id,)))
        await self._before("disconnect", cancel)
        self._sessions.pop(session.id, None)
        return self._result("disconnect")

    async def backup_files(
        self,
        session: TransportSession,
        paths: list[str],
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[TransportResult, dict[str, bytes]]:
        self.calls.append(("backup", (session.port.id, tuple(paths))))
        await self._before("backup", cancel)
        if (result := self._result("backup")).exit_code != 0:
            return result, {}
        current = self.files.setdefault(session.port.id, {})
        return result, {path: current[path] for path in paths if path in current}

    async def upload_files(
        self,
        session: TransportSession,
        files: dict[str, bytes],
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        self.calls.append(("upload", (session.port.id, tuple(sorted(files)))))
        await self._before("upload", cancel)
        current = self.files.setdefault(session.port.id, {})
        current.update(files)
        return self._result("upload")

    async def delete_files(
        self,
        session: TransportSession,
        paths: list[str],
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        self.calls.append(("delete", (session.port.id, tuple(paths))))
        await self._before("delete", cancel)
        result = self._result("delete")
        if result.exit_code == 0:
            current = self.files.setdefault(session.port.id, {})
            for path in paths:
                current.pop(path, None)
        return result

    async def read_file(
        self,
        session: TransportSession,
        path: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[TransportResult, bytes | None]:
        self.calls.append(("read", (session.port.id, path)))
        await self._before("read", cancel)
        result = self._result("read")
        return result, self.files.setdefault(session.port.id, {}).get(path)

    async def interrupt_runtime(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        self.calls.append(("interrupt_runtime", (session.port.id,)))
        await self._before("interrupt_runtime", cancel)
        return self._result("interrupt_runtime")

    async def start_runtime(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        self.calls.append(("start_runtime", (session.port.id,)))
        await self._before("start_runtime", cancel)
        return self._result("start_runtime")

    async def hard_reset(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        self.calls.append(("hard_reset", (session.port.id,)))
        await self._before("hard_reset", cancel)
        return self._result("hard_reset")

    async def monitor_terminal(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        on_output: Callable[[str], None],
    ) -> TransportResult:
        self.calls.append(("terminal", (session.port.id,)))
        await self._before("terminal", cancel)
        result = self._result("terminal")
        if result.exit_code != 0:
            return result
        for chunk in self.terminal_chunks.get(session.port.id, []):
            if cancel.is_set():
                return TransportResult(0, "mock terminal stopped")
            on_output(chunk)
            await asyncio.sleep(0)
        await cancel.wait()
        return TransportResult(0, "mock terminal stopped")

    async def write_terminal(
        self,
        session: TransportSession,
        data: bytes,
    ) -> TransportResult:
        # Do not retain terminal input in the mock call trace.
        self.calls.append(("terminal_write", (session.port.id, len(data))))
        return self._result("terminal_write")

    async def backup_flash_region(
        self,
        session: TransportSession,
        *,
        address: int,
        size: int,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[TransportResult, bytes | None]:
        self.calls.append(("backup_flash", (session.port.id, address, size)))
        await self._before("backup_flash", cancel)
        result = self._result("backup_flash")
        current = self.firmware.get(session.port.id, b"")
        return result, current[:size].ljust(size, b"\xff")

    async def inspect_firmware(
        self,
        path: Path,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        self.calls.append(("inspect_firmware", (path.name,)))
        await self._before("inspect_firmware", cancel)
        result = self._result("inspect_firmware")
        if result.exit_code == 0:
            content = path.read_bytes()
            result.data.update(
                {
                    "targetChip": "ESP32-S3",
                    "imageFormat": "mock-bin",
                    "defaultAddress": 0,
                    "sizeBytes": len(content),
                }
            )
        return result

    async def flash_firmware(
        self,
        session: TransportSession,
        path: Path,
        *,
        address: int,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        self.calls.append(("flash", (session.port.id, address, path.name)))
        await self._before("flash", cancel)
        result = self._result("flash")
        if result.exit_code == 0:
            self.firmware[session.port.id] = path.read_bytes()
        return result

    async def verify_firmware(
        self,
        session: TransportSession,
        path: Path,
        *,
        address: int,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        self.calls.append(("verify_firmware", (session.port.id, address, path.name)))
        await self._before("verify_firmware", cancel)
        result = self._result("verify_firmware")
        if result.exit_code == 0 and self.firmware.get(session.port.id) != path.read_bytes():
            return TransportResult(1, "firmware readback mismatch")
        return result

    async def _before(self, phase: str, cancel: asyncio.Event) -> None:
        delay = self.delays.get(phase, 0.0)
        if delay <= 0:
            if cancel.is_set():
                raise DeviceTransportCanceled()
            return
        try:
            await asyncio.wait_for(cancel.wait(), timeout=delay)
        except TimeoutError:
            pass
        if cancel.is_set():
            raise DeviceTransportCanceled()

    def _result(self, phase: str) -> TransportResult:
        code = self.failures.get(phase, 0)
        return TransportResult(code, f"mock {phase} exit={code}")


class SubprocessDeviceTransport:
    transport_mode = "LOCAL_SERIAL"
    evidence_eligible = True
    """Real adapter using fixed module invocations and no shell interpolation."""

    def __init__(self, scanner: Callable[[], list[DevicePort]] = list_serial_ports) -> None:
        self._scanner = scanner
        self._terminal_inputs: dict[str, asyncio.StreamWriter] = {}

    def resolve_port(self, port_id: str) -> DevicePort:
        try:
            ports = self._scanner()
        except SerialDiscoveryError as exc:
            raise DeviceTransportError(
                exc.code,
                exc.message,
                retryable=True,
            ) from exc
        for port in ports:
            if port.id == port_id or port.portName == port_id:
                return port
        raise DeviceTransportError("DEVICE_PORT_NOT_FOUND", "未找到最近扫描的串口。")

    async def scan_ports(self) -> list[DevicePort]:
        # pyserial/registry access is synchronous; keep it off the event loop.
        try:
            return await asyncio.to_thread(self._scanner)
        except SerialDiscoveryError as exc:
            raise DeviceTransportError(
                exc.code,
                exc.message,
                retryable=True,
            ) from exc

    async def connect(
        self,
        port: DevicePort,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[TransportSession, TransportResult]:
        if cancel.is_set():
            raise DeviceTransportCanceled()
        # Attachment is deliberately non-executing.  The previous implementation
        # ran an identity script here, so a busy main.py could block the service
        # before the cooperative Ctrl-C takeover had a chance to run.
        session = TransportSession(f"serial-session-{uuid.uuid4().hex}", port)
        return session, TransportResult(
            0,
            "serial attachment established; runtime and identity remain unverified",
        )

    async def probe_identity(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[DeviceIdentity, TransportResult]:
        result = await self._mpremote(
            session,
            ["resume", "exec", _IDENTITY_PROBE_SCRIPT],
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )
        if result.exit_code != 0:
            return DeviceIdentity(), result
        identity = _parse_identity_probe(result.output)
        if identity is None:
            return DeviceIdentity(), TransportResult(
                3,
                "identity probe returned no trusted sentinel",
            )
        result.data["identity"] = identity.as_dict()
        return identity, result

    async def disconnect(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        # mpremote commands are one-shot, so closing the process is the
        # transport-level disconnect operation.
        if cancel.is_set():
            raise DeviceTransportCanceled()
        return TransportResult(0, "serial session released")

    async def backup_files(
        self,
        session: TransportSession,
        paths: list[str],
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[TransportResult, dict[str, bytes]]:
        backup: dict[str, bytes] = {}
        for path in paths:
            _validate_remote_path(path)
            probe = await self._remote_file_exists(
                session,
                path,
                cancel=cancel,
                timeout_seconds=timeout_seconds,
            )
            if probe.exit_code != 0:
                return probe, backup
            if "__ZW_MISSING__" in probe.output:
                continue
            if "__ZW_EXISTS__" not in probe.output:
                return TransportResult(3, "remote existence probe returned no trusted sentinel"), backup
            with tempfile.TemporaryDirectory(prefix="zhangwen-device-backup-") as directory:
                local = Path(directory) / "file.bin"
                result = await self._mpremote(
                    session,
                    ["resume", "fs", "cp", f":{path}", str(local)],
                    cancel=cancel,
                    timeout_seconds=timeout_seconds,
                )
                if result.exit_code != 0:
                    return result, backup
                if not local.is_file():
                    return (
                        TransportResult(
                            3,
                            "backup copy reported success but produced no local file",
                        ),
                        backup,
                    )
                try:
                    backup[path] = local.read_bytes()
                except OSError:
                    return (
                        TransportResult(3, "backup copy could not be read locally"),
                        backup,
                    )
        return TransportResult(0, "backup complete"), backup

    async def _remote_file_exists(
        self,
        session: TransportSession,
        path: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        _validate_remote_path(path)
        script = "\n".join(
            [
                "import os",
                f"p={path!r}",
                "try:",
                " os.stat(p)",
                " print('__ZW_EXISTS__')",
                "except OSError as e:",
                " code=getattr(e, 'errno', e.args[0] if getattr(e, 'args', ()) else None)",
                " print('__ZW_MISSING__' if code == 2 else '__ZW_STAT_ERROR__')",
            ]
        )
        return await self._mpremote(
            session,
            ["resume", "exec", script],
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )

    async def upload_files(
        self,
        session: TransportSession,
        files: dict[str, bytes],
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        with tempfile.TemporaryDirectory(prefix="zhangwen-device-upload-") as directory:
            root = Path(directory)
            parent_paths = sorted(
                {
                    PurePosixPath(path).parent.as_posix()
                    for path in files
                    if PurePosixPath(path).parent.as_posix() != "."
                }
            )
            for parent in parent_paths:
                _validate_remote_path(parent)
                mkdir_script = "\n".join(
                    [
                        "import os",
                        f"p={parent!r}",
                        "try:",
                        " os.mkdir(p)",
                        "except OSError:",
                        " pass",
                    ]
                )
                mkdir_result = await self._mpremote(
                    session,
                    ["resume", "exec", mkdir_script],
                    cancel=cancel,
                    timeout_seconds=timeout_seconds,
                )
                if mkdir_result.exit_code != 0:
                    return mkdir_result
            for path, content in files.items():
                _validate_remote_path(path)
                local = root / (hashlib.sha256(path.encode()).hexdigest() + ".py")
                local.write_bytes(content)
                result = await self._mpremote(
                    session,
                    ["resume", "fs", "cp", str(local), f":{path}"],
                    cancel=cancel,
                    timeout_seconds=timeout_seconds,
                )
                if result.exit_code != 0:
                    return result
        return TransportResult(0, "upload complete")

    async def delete_files(
        self,
        session: TransportSession,
        paths: list[str],
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        for path in paths:
            _validate_remote_path(path)
            result = await self._mpremote(
                session,
                ["resume", "fs", "rm", f":{path}"],
                cancel=cancel,
                timeout_seconds=timeout_seconds,
            )
            if result.exit_code != 0:
                return result
        return TransportResult(0, "delete complete")

    async def read_file(
        self,
        session: TransportSession,
        path: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[TransportResult, bytes | None]:
        _validate_remote_path(path)
        with tempfile.TemporaryDirectory(prefix="zhangwen-device-read-") as directory:
            local = Path(directory) / "file.bin"
            result = await self._mpremote(
                session,
                ["resume", "fs", "cp", f":{path}", str(local)],
                cancel=cancel,
                timeout_seconds=timeout_seconds,
            )
            return result, local.read_bytes() if result.exit_code == 0 and local.is_file() else None

    async def interrupt_runtime(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        """Enter friendly REPL without resetting and interrupt Python code.

        Only the fixed Ctrl-C byte is written. Failure to observe a REPL prompt
        is fail-closed; callers may not escalate this to a hardware reset.
        """

        if cancel.is_set():
            raise DeviceTransportCanceled()
        argv = _tool_command(
            "mpremote",
            ["connect", session.port.portName, "resume", "repl"],
        )
        with tempfile.TemporaryDirectory(prefix="zhangwen-device-interrupt-") as directory:
            environment = _device_tool_environment(Path(directory))
            try:
                process = await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    env=environment,
                )
            except OSError as exc:
                return TransportResult(
                    None,
                    f"device runtime interrupt unavailable: {type(exc).__name__}",
                )
            assert process.stdin is not None
            self._terminal_inputs[session.id] = process.stdin

            output = bytearray()
            deadline = asyncio.get_running_loop().time() + timeout_seconds
            try:
                assert process.stdin is not None
                assert process.stdout is not None
                while True:
                    if cancel.is_set():
                        raise DeviceTransportCanceled(exit_code=process.returncode)
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise DeviceTransportTimedOut(
                            "安全停止设备程序超时。",
                            exit_code=process.returncode,
                        )
                    try:
                        process.stdin.write(b"\x03\x03")
                        await process.stdin.drain()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        return TransportResult(
                            process.returncode,
                            "安全中断通道在确认 REPL 前关闭。",
                        )
                    try:
                        chunk = await asyncio.wait_for(
                            process.stdout.read(1024),
                            timeout=min(0.4, remaining),
                        )
                    except TimeoutError:
                        continue
                    except (ConnectionResetError, OSError):
                        return TransportResult(
                            process.returncode,
                            "安全中断通道在确认 REPL 前关闭。",
                        )
                    if chunk:
                        output.extend(chunk)
                        if len(output) > MAX_COMMAND_OUTPUT:
                            del output[:-MAX_COMMAND_OUTPUT]
                        if _has_micropython_management_prompt(bytes(output)):
                            return TransportResult(0, "MicroPython 程序已安全停止，REPL 已就绪。")
                    elif process.returncode is not None:
                        return TransportResult(
                            process.returncode,
                            "未能在设备程序退出前确认 REPL。",
                        )
            except asyncio.CancelledError:
                raise
            finally:
                await _terminate_process(process)

    async def start_runtime(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        # A MicroPython soft reset clears the previous interpreter state but
        # does not toggle EN/RST or power. Raw soft reset skips main.py, so the
        # fixed follow-up explicitly imports the deployed entry point.
        return await self._mpremote(
            session,
            ["soft-reset", "exec", "--no-follow", "import main"],
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )

    async def hard_reset(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        # ``mpremote soft-reset`` keeps the board in raw REPL and MicroPython
        # intentionally skips main.py on that path.  A hard reset returns to
        # the normal boot.py -> main.py startup sequence, matching the reset
        # button without erasing Flash or reflashing firmware.
        return await self._mpremote(
            session,
            ["reset"],
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )

    async def monitor_terminal(
        self,
        session: TransportSession,
        *,
        cancel: asyncio.Event,
        on_output: Callable[[str], None],
    ) -> TransportResult:
        """Attach a read-only mpremote REPL process and forward device output.

        stdin stays open but the service never writes to it, so terminal keys,
        Ctrl-C, reset commands and arbitrary REPL input are outside this API.
        """

        if cancel.is_set():
            raise DeviceTransportCanceled()
        argv = _tool_command(
            "mpremote",
            ["connect", session.port.portName, "repl"],
        )
        with tempfile.TemporaryDirectory(prefix="zhangwen-device-terminal-") as directory:
            environment = _device_tool_environment(Path(directory))
            try:
                process = await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    env=environment,
                )
            except OSError as exc:
                return TransportResult(
                    None,
                    f"device terminal unavailable: {type(exc).__name__}",
                )

            async def forward_output() -> None:
                assert process.stdout is not None
                while True:
                    chunk = await process.stdout.read(1024)
                    if not chunk:
                        return
                    on_output(_sanitize_output(chunk))

            reader = asyncio.create_task(forward_output())
            cancellation = asyncio.create_task(cancel.wait())
            waiter = asyncio.create_task(process.wait())
            try:
                done, _ = await asyncio.wait(
                    {reader, cancellation, waiter},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if cancellation in done and cancel.is_set():
                    await _terminate_process(process)
                    await reader
                    return TransportResult(0, "serial terminal stopped")
                if reader in done and process.returncode is None:
                    await waiter
                return TransportResult(process.returncode, "serial terminal closed")
            except asyncio.CancelledError:
                await _terminate_process(process)
                raise
            finally:
                self._terminal_inputs.pop(session.id, None)
                if not reader.done():
                    reader.cancel()
                if not cancellation.done():
                    cancellation.cancel()
                if not waiter.done():
                    waiter.cancel()

    async def write_terminal(
        self,
        session: TransportSession,
        data: bytes,
    ) -> TransportResult:
        writer = self._terminal_inputs.get(session.id)
        if writer is None or writer.is_closing():
            return TransportResult(3, "serial terminal input is not available")
        try:
            writer.write(data)
            await writer.drain()
        except (BrokenPipeError, ConnectionError, OSError):
            return TransportResult(3, "serial terminal input failed")
        return TransportResult(0, "serial terminal input accepted")

    async def backup_flash_region(
        self,
        session: TransportSession,
        *,
        address: int,
        size: int,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> tuple[TransportResult, bytes | None]:
        with tempfile.TemporaryDirectory(prefix="zhangwen-device-flash-backup-") as directory:
            local = Path(directory) / "region.bin"
            result = await self._esptool(
                session,
                ["read-flash", hex(address), str(size), str(local)],
                cancel=cancel,
                timeout_seconds=timeout_seconds,
            )
            return result, local.read_bytes() if result.exit_code == 0 and local.is_file() else None

    async def inspect_firmware(
        self,
        path: Path,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        result = await self._run(
            _tool_command(
                "esptool",
                ["--chip", "esp32s3", "image-info", str(path)],
            ),
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )
        if result.exit_code == 0:
            chip = _parse_esptool_chip(result.output)
            if chip is not None:
                result.data.update(
                    {
                        "targetChip": chip,
                        "imageFormat": "esptool-image",
                        # image-info does not prove the target write address;
                        # the user must provide it during prepare.
                        "defaultAddress": None,
                    }
                )
        return result

    async def flash_firmware(
        self,
        session: TransportSession,
        path: Path,
        *,
        address: int,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        # Deliberately no erase-flash/erase-all argument is ever generated.
        return await self._esptool(
            session,
            ["write-flash", hex(address), str(path)],
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )

    async def verify_firmware(
        self,
        session: TransportSession,
        path: Path,
        *,
        address: int,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        return await self._esptool(
            session,
            ["verify-flash", hex(address), str(path)],
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )

    async def _mpremote(
        self,
        session: TransportSession,
        args: list[str],
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        return await self._run(
            _tool_command(
                "mpremote",
                ["connect", session.port.portName, *args],
            ),
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )

    async def _esptool(
        self,
        session: TransportSession,
        args: list[str],
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        return await self._run(
            _tool_command(
                "esptool",
                ["--chip", "esp32s3", "--port", session.port.portName, *args],
            ),
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )

    async def _run(
        self,
        argv: list[str],
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> TransportResult:
        if cancel.is_set():
            raise DeviceTransportCanceled()
        with tempfile.TemporaryDirectory(prefix="zhangwen-device-tool-") as directory:
            environment = _device_tool_environment(Path(directory))
            try:
                process = await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    env=environment,
                    # create_subprocess_exec never invokes a shell (equivalent to
                    # shell=False), and argv is assembled only from validated data.
                )
            except OSError as exc:
                return TransportResult(None, f"device tool unavailable: {type(exc).__name__}")

            communicate = asyncio.create_task(process.communicate())
            cancellation = asyncio.create_task(cancel.wait())
            try:
                done, _ = await asyncio.wait(
                    {communicate, cancellation},
                    timeout=timeout_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    await _terminate_process(process)
                    output, _ = await communicate
                    raise DeviceTransportTimedOut(exit_code=process.returncode)
                if cancellation in done and cancel.is_set():
                    await _terminate_process(process)
                    output, _ = await communicate
                    raise DeviceTransportCanceled(exit_code=process.returncode)
                output, _ = await communicate
                return TransportResult(process.returncode, _sanitize_output(output))
            except asyncio.CancelledError:
                await _terminate_process(process)
                raise
            finally:
                if not communicate.done():
                    communicate.cancel()
                if not cancellation.done():
                    cancellation.cancel()


def _tool_command(tool: str, args: list[str]) -> list[str]:
    if tool not in {"mpremote", "esptool"}:
        raise ValueError("unsupported packaged device tool")
    if getattr(sys, "frozen", False):
        return [sys.executable, tool, *args]
    return [sys.executable, "-m", tool, *args]


def _device_tool_environment(sandbox: Path) -> dict[str, str]:
    sandbox.mkdir(parents=True, exist_ok=True)
    esptool_config = sandbox / "esptool.cfg"
    esptool_config.write_text("[esptool]\n", encoding="utf-8", newline="\n")
    system_root = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR", "")
    environment = {
        "HOME": str(sandbox),
        "USERPROFILE": str(sandbox),
        "APPDATA": str(sandbox / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(sandbox / "AppData" / "Local"),
        "TEMP": str(sandbox),
        "TMP": str(sandbox),
        "ESPTOOL_CFGFILE": str(esptool_config),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
    }
    if system_root:
        environment.update(
            {
                "SYSTEMROOT": system_root,
                "WINDIR": system_root,
                "PATH": str(Path(system_root) / "System32"),
            }
        )
    if pathext := os.environ.get("PATHEXT"):
        environment["PATHEXT"] = pathext
    return environment


async def _terminate_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        process.terminate()
        await asyncio.wait_for(process.wait(), timeout=2.0)
    except (TimeoutError, ProcessLookupError):
        try:
            process.kill()
            await process.wait()
        except ProcessLookupError:
            pass


def _validate_remote_path(path: str) -> None:
    if not path or "\\" in path:
        raise DeviceTransportError("DEVICE_PATH_INVALID", "设备文件路径不安全。")
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts or path.startswith("."):
        raise DeviceTransportError("DEVICE_PATH_INVALID", "设备文件路径不安全。")


def _sanitize_output(raw: bytes | str) -> str:
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return text[-MAX_COMMAND_OUTPUT:]


def _has_micropython_management_prompt(output: bytes) -> bool:
    normalized = output.replace(b"\r\n", b"\n")
    return b">>> " in normalized or b"raw REPL; CTRL-B to exit\n>" in normalized


def _parse_identity_probe(output: str) -> DeviceIdentity | None:
    lines = output.splitlines()
    try:
        start = len(lines) - 1 - lines[::-1].index("__ZW_IDENTITY_V1__")
        end = lines.index("__ZW_IDENTITY_END__", start + 1)
    except ValueError:
        return None

    values: dict[str, str] = {}
    for line in lines[start + 1 : end]:
        key, separator, value = line.partition("=")
        if separator and key in {
            "implementation",
            "platform",
            "machine",
            "firmware",
            "uidHash",
            "unihiker_k10",
            "k10_base",
            "capabilities",
        }:
            values[key] = _clean_identity_value(value)
    if not values.get("implementation") or not values.get("platform"):
        return None

    modules = tuple(
        module
        for module in ("unihiker_k10", "k10_base")
        if values.get(module) == "1"
    )
    capabilities = tuple(
        capability
        for capability in ("screen", "button", "rgb")
        if capability in values.get("capabilities", "").split(",")
    )
    return DeviceIdentity(
        implementation=values["implementation"],
        platform=values["platform"],
        machine=values.get("machine", ""),
        firmware_version=values.get("firmware", ""),
        unique_id_hash=values.get("uidHash", ""),
        modules=modules,
        capabilities=capabilities,
    )


def _clean_identity_value(value: str) -> str:
    printable = re.sub(r"[^A-Za-z0-9_.:+(), /-]", "", value.strip())
    return printable[:160]


def _parse_esptool_chip(output: str) -> str | None:
    """Accept ESP32-S3 only from labeled esptool image-info lines."""

    patterns = (
        r"(?im)^\s*Chip(?:\s+ID)?\s*:[^\r\n]*\bESP32-S3\b",
        r"(?im)^\s*Detected\s+image\s+type\s*:[^\r\n]*\bESP32-S3\b",
        r"(?im)^\s*Image\s+for\s*:[^\r\n]*\bESP32-S3\b",
    )
    return "ESP32-S3" if any(re.search(pattern, output) for pattern in patterns) else None

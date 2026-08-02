"""Windows Job Object limits for the fixed CAD worker process."""

from __future__ import annotations

import os
import ctypes
from ctypes import Structure, byref, c_longlong, c_size_t
from ctypes import wintypes


JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
PROCESS_TERMINATE = 0x0001
PROCESS_SET_QUOTA = 0x0100


class _IoCounters(Structure):
    _fields_ = [
        ("ReadOperationCount", c_longlong),
        ("WriteOperationCount", c_longlong),
        ("OtherOperationCount", c_longlong),
        ("ReadTransferCount", c_longlong),
        ("WriteTransferCount", c_longlong),
        ("OtherTransferCount", c_longlong),
    ]


class _BasicLimitInformation(Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", c_longlong),
        ("PerJobUserTimeLimit", c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", c_size_t),
        ("MaximumWorkingSetSize", c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _ExtendedLimitInformation(Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", c_size_t),
        ("JobMemoryLimit", c_size_t),
        ("PeakProcessMemoryUsed", c_size_t),
        ("PeakJobMemoryUsed", c_size_t),
    ]


class WindowsJobObject:
    """Own a kill-on-close Job Object when running on Windows."""

    def __init__(self, pid: int, *, memory_bytes: int, cpu_seconds: int) -> None:
        self._handle: int | None = None
        if os.name != "nt":
            return
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.OpenProcess.restype = wintypes.HANDLE
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise OSError("CreateJobObjectW failed")
        info = _ExtendedLimitInformation()
        info.BasicLimitInformation.PerProcessUserTimeLimit = cpu_seconds * 10_000_000
        info.BasicLimitInformation.ActiveProcessLimit = 1
        info.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_PROCESS_TIME
            | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        info.ProcessMemoryLimit = memory_bytes
        configured = kernel32.SetInformationJobObject(
            job,
            JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            byref(info),
            sizeof_extended_limit_information(),
        )
        if not configured:
            kernel32.CloseHandle(job)
            raise OSError("SetInformationJobObject failed")
        process = kernel32.OpenProcess(
            PROCESS_TERMINATE | PROCESS_SET_QUOTA,
            False,
            pid,
        )
        if not process:
            kernel32.CloseHandle(job)
            raise OSError("OpenProcess failed for CAD worker")
        try:
            if not kernel32.AssignProcessToJobObject(job, process):
                raise OSError("AssignProcessToJobObject failed")
        except Exception:
            kernel32.CloseHandle(job)
            raise
        finally:
            kernel32.CloseHandle(process)
        self._handle = int(job)

    def close(self) -> None:
        if self._handle is not None and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self) -> "WindowsJobObject":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def sizeof_extended_limit_information() -> int:
    from ctypes import sizeof

    return sizeof(_ExtendedLimitInformation)

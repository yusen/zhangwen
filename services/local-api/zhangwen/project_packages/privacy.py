"""Privacy scanner for project package payloads."""

from __future__ import annotations

import re
from collections.abc import Mapping
from ipaddress import ip_address
from urllib.parse import urlsplit

from zhangwen.project_packages.models import (
    ProjectPackagePrivacyCheck,
    ProjectPackagePrivacyReport,
)


_SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "api-key",
        re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_\-]{6,}"),
        "疑似 API Key，项目包已阻止导出或导入。",
    ),
    (
        "authorization-header",
        re.compile(r"(?i)\bauthorization\b|\bbearer\s+[A-Za-z0-9._\-]{8,}"),
        "疑似认证头或 Bearer Token，项目包已阻止导出或导入。",
    ),
    (
        "secret-field",
        re.compile(r"(?i)\b(api[_-]?key|password|token|secret)\b\s*[:=]"),
        "疑似密钥字段，项目包已阻止导出或导入。",
    ),
    (
        "serial-port",
        re.compile(r"(?i)\bCOM\d+\b|/dev/tty[A-Za-z0-9._/-]*"),
        "疑似真实串口标识，项目包已阻止导出或导入。",
    ),
    (
        "absolute-path",
        re.compile(r"(?i)\b[A-Z]:[\\/]|/(Users|home|var|tmp)/[^\s\"']+"),
        "疑似个人绝对路径，项目包已阻止导出或导入。",
    ),
    (
        "espclaw-local-identifier",
        re.compile(
            r"(?i)(?:"
            r"\bespclaw_session_[A-Z0-9][A-Z0-9._:-]*|"
            r"\besp-claw:[A-Z0-9][A-Z0-9._:-]*"
            r")"
        ),
        "疑似 ESP-Claw 本机设备标识，项目包已阻止导出或导入。",
    ),
)

_HTTP_URL_PATTERN = re.compile(r"(?i)\bhttps?://[^\s\"'<>]+")
_PRIVATE_LAN_URL_MESSAGE = (
    "疑似 ESP-Claw 私网或 .local 地址，项目包已阻止导出或导入。"
)


def _contains_private_lan_http_url(content: str) -> bool:
    for match in _HTTP_URL_PATTERN.finditer(content):
        candidate = match.group(0).rstrip(".,);}")
        try:
            hostname = urlsplit(candidate).hostname
        except ValueError:
            continue
        if hostname is None:
            continue
        normalized_hostname = hostname.rstrip(".").lower()
        if normalized_hostname == "localhost" or normalized_hostname.endswith(
            ".local"
        ):
            return True
        try:
            address = ip_address(normalized_hostname)
        except ValueError:
            continue
        if address.is_private or address.is_link_local or address.is_loopback:
            return True
    return False


def scan_package_payload(files: Mapping[str, str]) -> ProjectPackagePrivacyReport:
    checks: list[ProjectPackagePrivacyCheck] = []
    for path, content in files.items():
        for dimension, pattern, message in _SENSITIVE_PATTERNS:
            if pattern.search(content):
                checks.append(
                    ProjectPackagePrivacyCheck(
                        dimension=dimension,
                        severity="FAIL",
                        message=message,
                        path=path,
                    )
                )
        if _contains_private_lan_http_url(content):
            checks.append(
                ProjectPackagePrivacyCheck(
                    dimension="private-lan-url",
                    severity="FAIL",
                    message=_PRIVATE_LAN_URL_MESSAGE,
                    path=path,
                )
            )
    if not checks:
        checks.append(
            ProjectPackagePrivacyCheck(
                dimension="privacy-scan",
                severity="PASS",
                message=(
                    "未发现 API Key、认证头、真实串口标识、ESP-Claw 私网信息"
                    "或个人绝对路径。"
                ),
                path=None,
            )
        )
    return ProjectPackagePrivacyReport(
        ok=not any(check.severity == "FAIL" for check in checks),
        checks=checks,
    )

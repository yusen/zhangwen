"""SSRF-safe validation for user-configurable OpenAI-compatible endpoints."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable
from urllib.parse import urlsplit, urlunsplit


class ProviderUrlError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


AddressResolver = Callable[[str, int], Iterable[str]]

_BLOCKED_HOSTS = {
    "metadata",
    "metadata.google.internal",
    "instance-data",
    "169.254.169.254",
    "100.100.100.200",
    "fd00:ec2::254",
}


def validate_provider_base_url(
    value: str,
    *,
    allow_private_network: bool,
    private_network_confirmed: bool,
    resolve_dns: bool = False,
    resolver: AddressResolver | None = None,
) -> str:
    """Return a canonical safe base URL or raise a user-safe error.

    Redirects are disabled by the provider transport, so every actual target is
    this validated origin. DNS resolution is repeated immediately before a
    connection test or model request boundary.
    """

    candidate = value.strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise ProviderUrlError("INVALID_BASE_URL", "模型服务地址格式无效。") from exc
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ProviderUrlError(
            "UNSAFE_BASE_URL_SCHEME",
            "模型服务地址只允许 HTTP(S)，不能使用 file:、ftp: 等协议。",
        )
    if not parsed.hostname:
        raise ProviderUrlError("INVALID_BASE_URL", "模型服务地址缺少主机名。")
    if parsed.username is not None or parsed.password is not None:
        raise ProviderUrlError(
            "BASE_URL_CREDENTIALS_BLOCKED",
            "模型服务地址不能包含用户名或密码。",
        )
    if parsed.query or parsed.fragment:
        raise ProviderUrlError(
            "BASE_URL_SUFFIX_BLOCKED",
            "模型服务基础地址不能包含查询参数或片段。",
        )

    host = parsed.hostname.rstrip(".").lower()
    if host in _BLOCKED_HOSTS or host.endswith(".metadata.google.internal"):
        raise ProviderUrlError(
            "METADATA_ADDRESS_BLOCKED",
            "该地址属于系统元数据网络，不能作为模型服务地址。",
        )

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    try:
        addresses.append(ipaddress.ip_address(host))
    except ValueError:
        if host == "localhost" or host.endswith(".localhost"):
            addresses.append(ipaddress.ip_address("127.0.0.1"))
        elif resolve_dns:
            resolved = (resolver or _resolve)(host, port or (443 if scheme == "https" else 80))
            try:
                addresses.extend(ipaddress.ip_address(item) for item in resolved)
            except ValueError as exc:
                raise ProviderUrlError(
                    "DNS_RESOLUTION_INVALID",
                    "模型服务域名解析到了无效地址。",
                ) from exc
            if not addresses:
                raise ProviderUrlError(
                    "DNS_UNAVAILABLE",
                    "无法解析模型服务域名，请检查网络或地址。",
                )

    for address in addresses:
        _validate_address(
            address,
            allow_private_network=allow_private_network,
            private_network_confirmed=private_network_confirmed,
        )

    is_loopback = bool(addresses) and all(address.is_loopback for address in addresses)
    if scheme == "http" and not is_loopback:
        raise ProviderUrlError(
            "EXTERNAL_HTTP_BLOCKED",
            "外部模型服务必须使用 HTTPS；HTTP 只允许本机 Loopback。",
        )

    netloc = parsed.netloc
    canonical_path = parsed.path.rstrip("/")
    return urlunsplit((scheme, netloc, canonical_path, "", ""))


def _validate_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    allow_private_network: bool,
    private_network_confirmed: bool,
) -> None:
    if str(address) in _BLOCKED_HOSTS or address.is_link_local:
        raise ProviderUrlError(
            "LINK_LOCAL_ADDRESS_BLOCKED",
            "Link-local 和系统元数据地址不能作为模型服务地址。",
        )
    if address.is_multicast or address.is_unspecified or address.is_reserved:
        raise ProviderUrlError(
            "SPECIAL_ADDRESS_BLOCKED",
            "该特殊网络地址不能作为模型服务地址。",
        )
    if address.is_loopback:
        return
    if address.is_private and not (
        allow_private_network and private_network_confirmed
    ):
        raise ProviderUrlError(
            "PRIVATE_NETWORK_CONFIRMATION_REQUIRED",
            "家庭局域网地址需要显式确认后才能使用。",
        )


def _resolve(host: str, port: int) -> list[str]:
    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ProviderUrlError(
            "DNS_UNAVAILABLE",
            "无法解析模型服务域名，请检查网络或地址。",
        ) from exc
    return list(dict.fromkeys(str(record[4][0]) for record in records))

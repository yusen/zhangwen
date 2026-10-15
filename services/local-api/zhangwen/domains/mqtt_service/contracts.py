"""Topic-contract validation, ACL compilation, and private config rendering."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
from collections.abc import Iterable
from collections.abc import Mapping

from zhangwen.domains.mqtt_service.models import (
    MqttMode,
    MqttServiceValidationError,
    MqttTopicDirection,
    MqttTopicRule,
)


def namespace_for_work(work_id: str) -> str:
    return f"zhangwen/1/{work_id}"


def default_topic_rules(work_id: str) -> list[MqttTopicRule]:
    namespace = namespace_for_work(work_id)
    return [
        MqttTopicRule(
            id="telemetry",
            topicPattern=f"{namespace}/device/+/telemetry/+",
            direction=MqttTopicDirection.SUBSCRIBE,
            payloadSchema={"type": "object"},
            maxPayloadBytes=4096,
            maxRateHz=10,
            qos=0,
            retain=False,
            principal="work-runtime",
        ),
        MqttTopicRule(
            id="state",
            topicPattern=f"{namespace}/device/+/state/+",
            direction=MqttTopicDirection.SUBSCRIBE,
            payloadSchema={"type": "object"},
            maxPayloadBytes=4096,
            maxRateHz=2,
            qos=1,
            retain=True,
            principal="work-runtime",
        ),
        MqttTopicRule(
            id="commands",
            topicPattern=f"{namespace}/device/+/command/+",
            direction=MqttTopicDirection.PUBLISH,
            payloadSchema={
                "type": "object",
                "required": ["commandId"],
                "properties": {"commandId": {"type": "string"}},
            },
            maxPayloadBytes=4096,
            maxRateHz=10,
            qos=1,
            retain=False,
            principal="work-runtime",
        ),
        MqttTopicRule(
            id="service-events",
            topicPattern=f"{namespace}/service/+/event/+",
            direction=MqttTopicDirection.SUBSCRIBE,
            payloadSchema={"type": "object"},
            maxPayloadBytes=4096,
            maxRateHz=2,
            qos=1,
            retain=False,
            principal="work-runtime",
        ),
    ]


def validate_and_compile(
    work_id: str,
    rules: Iterable[MqttTopicRule],
) -> tuple[list[MqttTopicRule], list[dict[str, object]], str]:
    normalized = list(rules)
    if not normalized:
        raise MqttServiceValidationError("设备通信规则不能为空。")
    namespace = namespace_for_work(work_id)
    seen_ids: set[str] = set()
    seen_acl: set[tuple[str, str, str]] = set()
    compiled: list[dict[str, object]] = []
    for rule in normalized:
        if rule.id in seen_ids:
            raise MqttServiceValidationError("设备通信规则标识不能重复。")
        seen_ids.add(rule.id)
        _validate_pattern(rule, namespace)
        _validate_schema_definition(rule.payload_schema)
        if rule.qos == 2:
            raise MqttServiceValidationError("首版设备通信只允许 QoS 0 或 1。")
        lowered = rule.topic_pattern.lower()
        topic_segments = lowered.split("/")
        if "telemetry" in topic_segments and (rule.qos != 0 or rule.retain):
            raise MqttServiceValidationError("实时采样必须使用 QoS 0 且不得保留。")
        if "command" in topic_segments or "commands" in topic_segments:
            if rule.qos != 1 or rule.retain:
                raise MqttServiceValidationError("控制消息必须使用 QoS 1 且不得保留。")
            required = rule.payload_schema.get("required")
            if not isinstance(required, list) or "commandId" not in required:
                raise MqttServiceValidationError("控制消息必须声明 commandId 幂等字段。")
        for access in _acl_access(rule.direction):
            key = (rule.principal, access, rule.topic_pattern)
            if key in seen_acl:
                continue
            seen_acl.add(key)
            compiled.append(
                {
                    "principal": rule.principal,
                    "access": access,
                    "topic": rule.topic_pattern,
                }
            )
    compiled.sort(key=lambda item: (str(item["principal"]), str(item["access"]), str(item["topic"])))
    digest = hashlib.sha256(_dump(compiled).encode("utf-8")).hexdigest()
    return normalized, compiled, digest


def render_private_config(
    *,
    instance_id: str,
    work_id: str,
    mode: MqttMode,
    listen_host: str | None,
    listen_port: int | None,
    external_endpoint: str | None,
    external_tls: bool,
    service_package_revision_id: str,
    topic_contract_revision_id: str,
    acl: list[dict[str, object]],
) -> str:
    value = {
        "schema": "zhangwen.mqtt-service-config/v1",
        "instanceId": instance_id,
        "workId": work_id,
        "mode": mode.value,
        "servicePackageRevisionId": service_package_revision_id,
        "topicContractRevisionId": topic_contract_revision_id,
        "listen": (
            {"host": listen_host, "port": listen_port}
            if listen_host is not None and listen_port is not None
            else None
        ),
        "external": (
            {"endpoint": external_endpoint, "tls": external_tls}
            if external_endpoint is not None
            else None
        ),
        "allowAnonymous": False,
        "namespace": namespace_for_work(work_id),
        "acl": acl,
    }
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def validate_lan_host(
    host: str,
    *,
    available_hosts: set[str] | None = None,
) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise MqttServiceValidationError("家庭网络模式必须使用具体的私有 IP 地址。") from exc
    if not address.is_private or address.is_loopback or address.is_unspecified:
        raise MqttServiceValidationError("家庭网络模式只能绑定具体的私有网络地址。")
    local_addresses = available_hosts if available_hosts is not None else _local_interface_addresses()
    if str(address) not in local_addresses:
        raise MqttServiceValidationError("家庭网络地址必须属于当前可用的本机网络接口。")


def _local_interface_addresses() -> set[str]:
    """Return only addresses the OS currently resolves for this host; fail closed."""

    addresses: set[str] = set()
    try:
        candidates = socket.getaddrinfo(
            socket.gethostname(),
            None,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except OSError:
        return addresses
    for candidate in candidates:
        value = str(candidate[4][0]).split("%", 1)[0]
        try:
            addresses.add(str(ipaddress.ip_address(value)))
        except ValueError:
            continue
    return addresses


def _validate_pattern(rule: MqttTopicRule, namespace: str) -> None:
    pattern = rule.topic_pattern
    if not pattern.startswith(f"{namespace}/"):
        raise MqttServiceValidationError("消息范围必须限制在当前作品命名空间内。")
    if pattern.startswith("$") or "/$" in pattern:
        raise MqttServiceValidationError("禁止访问系统消息主题。")
    segments = pattern.split("/")
    if any(not segment for segment in segments):
        raise MqttServiceValidationError("消息主题不能包含空层级。")
    for index, segment in enumerate(segments):
        if "#" in segment and (segment != "#" or index != len(segments) - 1):
            raise MqttServiceValidationError("多层通配符只能作为最后一个完整层级。")
        if "+" in segment and segment != "+":
            raise MqttServiceValidationError("单层通配符必须占据完整层级。")


def topic_matches(pattern: str, topic: str) -> bool:
    """Match one concrete MQTT topic against one validated contract pattern."""

    if "+" in topic or "#" in topic or topic.startswith("$"):
        return False
    pattern_segments = pattern.split("/")
    topic_segments = topic.split("/")
    for index, expected in enumerate(pattern_segments):
        if expected == "#":
            return index == len(pattern_segments) - 1
        if index >= len(topic_segments):
            return False
        if expected != "+" and expected != topic_segments[index]:
            return False
    return len(pattern_segments) == len(topic_segments)


def validate_payload_against_schema(
    payload: Mapping[str, object],
    schema: Mapping[str, object],
) -> None:
    """Validate the bounded JSON-Schema subset accepted by Topic Contracts."""

    _validate_schema_value(payload, schema, path="payload")


def _validate_schema_definition(schema: Mapping[str, object]) -> None:
    schema_type = schema.get("type", "object")
    if schema_type not in {"object", "array", "string", "number", "integer", "boolean", "null"}:
        raise MqttServiceValidationError("通信规则包含不支持的 payload schema 类型。")
    required = schema.get("required", [])
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        raise MqttServiceValidationError("通信规则 payload schema 的 required 必须是字符串数组。")
    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping):
        raise MqttServiceValidationError("通信规则 payload schema 的 properties 必须是对象。")
    for child in properties.values():
        if not isinstance(child, Mapping):
            raise MqttServiceValidationError("通信规则 payload schema 的属性定义必须是对象。")
        _validate_schema_definition(child)
    items = schema.get("items")
    if items is not None:
        if not isinstance(items, Mapping):
            raise MqttServiceValidationError("通信规则 payload schema 的 items 必须是对象。")
        _validate_schema_definition(items)


def _validate_schema_value(value: object, schema: Mapping[str, object], *, path: str) -> None:
    expected = schema.get("type", "object")
    valid = {
        "object": isinstance(value, Mapping),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(str(expected), False)
    if not valid:
        raise MqttServiceValidationError(f"{path} 不符合当前通信规则声明的类型。")
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        raise MqttServiceValidationError(f"{path} 不在当前通信规则允许的取值中。")
    if isinstance(value, Mapping):
        required = schema.get("required", [])
        if isinstance(required, list):
            missing = [item for item in required if isinstance(item, str) and item not in value]
            if missing:
                raise MqttServiceValidationError(
                    f"{path} 缺少当前通信规则要求的字段：{', '.join(missing)}。"
                )
        properties = schema.get("properties", {})
        if isinstance(properties, Mapping):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, Mapping):
                    _validate_schema_value(value[key], child_schema, path=f"{path}.{key}")
            if schema.get("additionalProperties") is False:
                extras = sorted(str(key) for key in value if key not in properties)
                if extras:
                    raise MqttServiceValidationError(
                        f"{path} 包含当前通信规则未声明的字段：{', '.join(extras)}。"
                    )
    elif isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                _validate_schema_value(item, item_schema, path=f"{path}[{index}]")


def _acl_access(direction: MqttTopicDirection) -> tuple[str, ...]:
    if direction is MqttTopicDirection.PUBLISH:
        return ("write",)
    if direction is MqttTopicDirection.SUBSCRIBE:
        return ("read",)
    return ("read", "write")


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

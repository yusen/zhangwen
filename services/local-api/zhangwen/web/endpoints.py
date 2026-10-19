"""User-selected OpenAI-compatible endpoints. Never forward a key on redirects."""
from urllib.parse import urlsplit

DEFAULT_BASE_URL = "https://api.deepseek.com"


def base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parts = urlsplit(value)
    if (len(value) > 500 or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment
            or any(ord(c) < 33 or ord(c) > 126 for c in value)
            or parts.scheme not in {"https", "http"}
            or (parts.scheme == "http" and parts.hostname not in {"localhost", "127.0.0.1", "::1"})):
        raise ValueError("填写 HTTPS API 基础地址；本机服务可使用 http://localhost 或 127.0.0.1。")
    _ = parts.port  # validate port
    if parts.path.endswith('/chat/completions'):
        raise ValueError("请填写基础地址，不包含 /chat/completions。")
    return value


def is_deepseek(value: str) -> bool:
    return value in {DEFAULT_BASE_URL, DEFAULT_BASE_URL + "/v1"}


def configured(settings: dict[str, str]) -> bool:
    return bool(settings["apiKey"]) or urlsplit(settings.get("baseUrl", DEFAULT_BASE_URL)).hostname in {"localhost", "127.0.0.1", "::1"}


def resolve_settings(current: dict[str, str], request) -> dict[str, str]:
    endpoint = request.baseUrl or current.get("baseUrl", DEFAULT_BASE_URL)
    if endpoint != current.get("baseUrl", DEFAULT_BASE_URL) and request.apiKey is None:
        raise ValueError("更换 API 地址时请填写新服务的 Key；无 Key 的本机服务请明确清除 Key。")
    from .models import current_ai_model
    return {"apiKey": current["apiKey"] if request.apiKey is None else request.apiKey,
            "model": current_ai_model(request.model) if is_deepseek(endpoint) else request.model,
            "baseUrl": endpoint}

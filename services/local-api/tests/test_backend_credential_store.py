from __future__ import annotations

from zhangwen.security.credentials import BackendCredentialStore, MemoryCredentialStore


def test_backend_environment_key_is_read_without_frontend_or_persistence(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ZHANGWEN_DEEPSEEK_API_KEY", "fake-environment-test-key")
    store = BackendCredentialStore()

    assert store.get_password("zhangwen.deepseek", "default") == "fake-environment-test-key"


def test_backend_credential_store_falls_back_to_configured_secure_adapter(
    monkeypatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_DEEPSEEK_API_KEY", raising=False)
    store = BackendCredentialStore()
    memory = MemoryCredentialStore()
    memory.set_password("zhangwen.deepseek", "default", "fake-secure-store-key")
    store._windows = memory

    assert store.get_password("zhangwen.deepseek", "default") == "fake-secure-store-key"


def test_backend_environment_keys_are_selected_per_provider(monkeypatch) -> None:
    monkeypatch.setenv("ZHANGWEN_QWEN_API_KEY", "fake-qwen-key")
    monkeypatch.setenv("ZHANGWEN_GLM_API_KEY", "fake-glm-key")
    monkeypatch.setenv("ZHANGWEN_KIMI_API_KEY", "fake-kimi-key")
    store = BackendCredentialStore()

    assert store.get_password("zhangwen.qwen", "default") == "fake-qwen-key"
    assert store.get_password("zhangwen.glm", "default") == "fake-glm-key"
    assert store.get_password("zhangwen.kimi", "default") == "fake-kimi-key"

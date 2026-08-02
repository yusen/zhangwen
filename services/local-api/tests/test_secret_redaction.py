from zhangwen.security.redaction import mask_api_key, redact_mapping, redact_text


def test_redact_text_masks_api_key_and_bearer() -> None:
    redacted = redact_text("Authorization: Bearer token-value sk-test-secret-value")

    assert "token-value" not in redacted
    assert "sk-test-secret-value" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_mapping_masks_sensitive_keys() -> None:
    redacted = redact_mapping({"apiKey": "sk-test-secret-value", "name": "ok"})

    assert redacted["apiKey"] == "[REDACTED]"
    assert redacted["name"] == "ok"


def test_mask_api_key() -> None:
    assert mask_api_key("sk-test-secret-value") == "sk-****alue"

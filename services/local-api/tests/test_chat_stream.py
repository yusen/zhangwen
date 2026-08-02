from zhangwen.chat.sessions import ChatSessionRegistry


def test_session_registry_cancels_request() -> None:
    registry = ChatSessionRegistry()
    token = registry.create("req_1", abort_previous=False)

    assert token.canceled is False
    assert registry.cancel("req_1") is True
    assert token.canceled is True


def test_session_registry_abort_previous() -> None:
    registry = ChatSessionRegistry()
    old = registry.create("req_1", abort_previous=False)
    new = registry.create("req_2", abort_previous=True)

    assert old.canceled is True
    assert new.canceled is False
    assert registry.cancel("req_1") is False
    assert registry.cancel("req_2") is True

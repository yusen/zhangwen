from __future__ import annotations

from contextvars import ContextVar, Token


_owner_subject: ContextVar[str | None] = ContextVar("zhangwen_owner_subject", default=None)


def current_owner_subject() -> str | None:
    return _owner_subject.get()


def bind_owner_subject(subject: str) -> Token[str | None]:
    return _owner_subject.set(subject)


def reset_owner_subject(token: Token[str | None]) -> None:
    _owner_subject.reset(token)

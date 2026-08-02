"""Active chat session registry."""

from zhangwen.llm.gateway import CancelToken


class ChatSessionRegistry:
    def __init__(self) -> None:
        self._tokens: dict[str, CancelToken] = {}

    def create(self, request_id: str, *, abort_previous: bool) -> CancelToken:
        if abort_previous:
            for token in self._tokens.values():
                token.cancel()
            self._tokens.clear()
        token = CancelToken()
        self._tokens[request_id] = token
        return token

    def cancel(self, request_id: str) -> bool:
        token = self._tokens.get(request_id)
        if not token:
            return False
        token.cancel()
        return True

    def remove(self, request_id: str) -> None:
        self._tokens.pop(request_id, None)

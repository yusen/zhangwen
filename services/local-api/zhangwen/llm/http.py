"""FastAPI mapping for provider-neutral LLM errors."""

from fastapi import HTTPException

from zhangwen.llm.contracts import LLMError, LLMErrorCode
from zhangwen.llm.structured import StructuredLLMError


def llm_http_exception(error: LLMError | StructuredLLMError) -> HTTPException:
    llm_error = error.error if isinstance(error, StructuredLLMError) else error
    return HTTPException(
        status_code=_status_code(llm_error.code),
        detail=llm_error.model_dump(mode="json", exclude_none=True),
    )


def _status_code(code: LLMErrorCode) -> int:
    if code == LLMErrorCode.CONFIG_MISSING:
        return 400
    if code == LLMErrorCode.AUTH_FAILED:
        return 401
    if code == LLMErrorCode.INSUFFICIENT_BALANCE:
        return 402
    if code == LLMErrorCode.RATE_LIMITED:
        return 429
    if code == LLMErrorCode.CANCELED:
        return 409
    if code in {
        LLMErrorCode.INVALID_REQUEST,
        LLMErrorCode.INVALID_PARAMETERS,
        LLMErrorCode.LLM_OUTPUT_INVALID,
        LLMErrorCode.LOCAL_OUTPUT_REJECTED,
    }:
        return 422
    if code == LLMErrorCode.TIMEOUT:
        return 504
    return 503

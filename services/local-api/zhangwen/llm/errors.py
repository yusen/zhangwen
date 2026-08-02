"""Provider-neutral LLM error mapping."""

from zhangwen.llm.contracts import LLMError, LLMErrorCode, UserAction


def make_llm_error(
    code: LLMErrorCode,
    provider_status: int | None = None,
) -> LLMError:
    messages = {
        LLMErrorCode.CONFIG_MISSING: ("请先在设置中配置所选模型服务的 API Key。", False),
        LLMErrorCode.LLM_OUTPUT_INVALID: (
            "云端返回的结构化内容连续两次不完整。原需求已保留，可直接重新生成；若反复出现，请检查模型设置。",
            True,
        ),
        LLMErrorCode.LOCAL_OUTPUT_REJECTED: (
            "生成结果未通过当前工程约束或安全边界，未写入工程产物。原需求本身不需要修改，可按原需求重新生成。",
            True,
        ),
        LLMErrorCode.GENERATION_INTERRUPTED: (
            "上次生成因应用或本地服务中断而停止。原需求已保留，可以继续生成。",
            True,
        ),
        LLMErrorCode.INVALID_REQUEST: ("请求格式有误，请稍后重试或更新应用。", False),
        LLMErrorCode.AUTH_FAILED: ("API Key 验证失败，请检查当前服务商的密钥。", False),
        LLMErrorCode.INSUFFICIENT_BALANCE: ("模型服务账户余额不足，请充值后重试。", False),
        LLMErrorCode.INVALID_PARAMETERS: ("模型参数不受支持，请检查模型或思考模式设置。", False),
        LLMErrorCode.RATE_LIMITED: ("请求过于频繁，请稍后再试。", True),
        LLMErrorCode.SERVER_ERROR: ("模型服务暂时出错，请稍后重试。", True),
        LLMErrorCode.SERVICE_BUSY: ("模型服务当前繁忙，请稍后重试。", True),
        LLMErrorCode.NETWORK_UNAVAILABLE: ("本机网络不可用，请检查网络连接。", True),
        LLMErrorCode.TIMEOUT: ("请求超时，请稍后重试或调大超时时间。", True),
        LLMErrorCode.CANCELED: ("已停止生成。", True),
        LLMErrorCode.SIDECAR_UNAVAILABLE: ("本地服务暂时不可用，正在尝试自动恢复。", True),
        LLMErrorCode.QUESTION_NOT_FOUND: ("这个问题已不属于当前对话，请回到最新问题继续。", False),
        LLMErrorCode.QUESTION_ALREADY_ANSWERED: ("这个问题已经回答过，请继续处理最新问题。", False),
        LLMErrorCode.OPTION_NOT_ALLOWED: ("该选项不属于当前问题。", False),
        LLMErrorCode.CLARIFICATION_INCOMPLETE: ("请完成本轮全部必答问题后再提交。", False),
        LLMErrorCode.DUPLICATE_QUESTION_ANSWER: ("同一问题不能在一次提交中重复回答。", False),
        LLMErrorCode.STALE_CONVERSATION_TURN: ("这次回答已过期，请根据当前最新消息重新操作。", False),
        LLMErrorCode.PROJECT_CONTEXT_MISMATCH: ("项目或会话上下文不匹配，请重新打开当前项目后重试。", False),
        LLMErrorCode.DUPLICATE_TURN: ("这次请求已经提交，正在复用已有结果。", False),
        LLMErrorCode.UNKNOWN: ("请求失败，请稍后重试。", True),
    }
    message, retryable = messages[code]
    actions = [UserAction(id="retry", label="重新生成")] if retryable else []
    if code == LLMErrorCode.LLM_OUTPUT_INVALID:
        actions = [
            UserAction(id="retry", label="重新生成"),
            UserAction(id="open_settings", label="检查模型设置"),
        ]
    elif code == LLMErrorCode.LOCAL_OUTPUT_REJECTED:
        actions = [UserAction(id="retry", label="按原需求重试")]
    elif code == LLMErrorCode.GENERATION_INTERRUPTED:
        actions = [
            UserAction(id="retry", label="继续生成"),
            UserAction(id="revise_request", label="修改原需求"),
        ]
    elif code in {LLMErrorCode.CONFIG_MISSING, LLMErrorCode.AUTH_FAILED}:
        actions = [UserAction(id="open_settings", label="打开设置")]
    return LLMError(
        code=code,
        message=message,
        retryable=retryable,
        userActions=actions,
        providerStatus=provider_status,
    )


def map_http_status(status_code: int) -> LLMError:
    mapping = {
        400: LLMErrorCode.INVALID_REQUEST,
        401: LLMErrorCode.AUTH_FAILED,
        402: LLMErrorCode.INSUFFICIENT_BALANCE,
        422: LLMErrorCode.INVALID_PARAMETERS,
        429: LLMErrorCode.RATE_LIMITED,
        500: LLMErrorCode.SERVER_ERROR,
        503: LLMErrorCode.SERVICE_BUSY,
    }
    return make_llm_error(
        mapping.get(status_code, LLMErrorCode.UNKNOWN),
        status_code,
    )

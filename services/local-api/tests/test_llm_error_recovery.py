from zhangwen.llm.contracts import LLMErrorCode
from zhangwen.llm.errors import make_llm_error


def test_generation_failures_return_specific_recovery_actions() -> None:
    local_error = make_llm_error(LLMErrorCode.LOCAL_OUTPUT_REJECTED)
    invalid_error = make_llm_error(LLMErrorCode.LLM_OUTPUT_INVALID)
    interrupted_error = make_llm_error(LLMErrorCode.GENERATION_INTERRUPTED)

    assert [(action.id, action.label) for action in local_error.userActions] == [
        ("retry", "按原需求重试"),
    ]
    assert [(action.id, action.label) for action in invalid_error.userActions] == [
        ("retry", "重新生成"),
        ("open_settings", "检查模型设置"),
    ]
    assert [(action.id, action.label) for action in interrupted_error.userActions] == [
        ("retry", "继续生成"),
        ("revise_request", "修改原需求"),
    ]
    assert "原需求本身不需要修改" in local_error.message
    assert "原需求已保留" in invalid_error.message
    assert "原需求已保留" in interrupted_error.message

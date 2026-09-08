from memora_agent.schema.chat import ChatRequest


def test_request_can_select_model() -> None:
    request = ChatRequest(
        message="你好",
        provider_type="qwen",
        model_name="qwen3.8-max",
    )

    assert request.provider_type == "qwen"
    assert request.model_name == "qwen3.8-max"


def test_message_only_request_is_allowed() -> None:
    request = ChatRequest(message="你好")

    assert request.provider_type is None
    assert request.model_name is None

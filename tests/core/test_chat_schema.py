from memora_agent.schema.chat import ChatRequest


def test_request_can_select_model() -> None:
    request = ChatRequest(
        message="你好",
        provider_type="openai",
        model_name="deepseek-chat",
    )

    assert request.provider_type == "openai"
    assert request.model_name == "deepseek-chat"


def test_message_only_request_is_allowed() -> None:
    request = ChatRequest(message="你好")

    assert request.provider_type is None
    assert request.model_name is None

import pytest
from pydantic import ValidationError

from app.schema.chat import (
    ChatRequest,
    MessageDeltaEvent,
    MessageFailedEvent,
    MessageStartedEvent,
)


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


def test_history_defaults_to_empty() -> None:
    request = ChatRequest(message="你好")

    assert request.history == []


def test_history_accepts_user_and_assistant() -> None:
    request = ChatRequest(
        message="然后呢",
        history=[
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，有什么可以帮你"},
        ],
    )

    assert [m.role for m in request.history] == ["user", "assistant"]


def test_history_rejects_unknown_role() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(
            message="你好",
            history=[{"role": "system", "content": "x"}],
        )


def test_delta_event_requires_seq_and_content() -> None:
    with pytest.raises(ValidationError):
        MessageDeltaEvent(content="缺 seq")

    event = MessageDeltaEvent(seq=1, content="根")
    assert event.seq == 1
    assert event.content == "根"


def test_started_and_failed_event_shapes() -> None:
    assert MessageStartedEvent(message_id="m1").message_id == "m1"
    assert MessageStartedEvent(message_id="m1").conversation_id is None
    started = MessageStartedEvent(message_id="m1", conversation_id=7)
    assert started.conversation_id == 7
    assert MessageFailedEvent(message="出错了").message == "出错了"


def test_conversation_id_defaults_to_none() -> None:
    request = ChatRequest(message="你好")
    assert request.conversation_id is None


def test_conversation_id_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="你好", conversation_id=0)

import json

from app.queue.ingest import (
    INGEST_ROUTING_KEY,
    build_ingest_payload,
    encode_ingest_message,
    publish_to_exchange,
)


def test_build_ingest_payload_omits_download_url() -> None:
    payload = build_ingest_payload(
        knowledge_file_id=42,
        object_key="abc/notes.pdf",
        filename="notes.pdf",
        user_id=1,
        username="tester",
        size=1024,
    )
    assert payload == {
        "knowledge_file_id": 42,
        "object_key": "abc/notes.pdf",
        "filename": "notes.pdf",
        "user_id": 1,
        "username": "tester",
        "size": 1024,
    }
    assert "download_url" not in payload
    assert "file_url" not in payload


def test_encode_ingest_message_is_persistent_json() -> None:
    payload = build_ingest_payload(1, "k", "f.txt", 2, "u", 3)
    message = encode_ingest_message(payload)
    assert json.loads(message.body.decode("utf-8")) == payload
    assert message.content_type == "application/json"


def test_publish_to_exchange_uses_ingest_routing_key() -> None:
    import asyncio

    captured: list[tuple[bytes, str]] = []

    class FakeExchange:
        async def publish(self, message, routing_key: str) -> None:
            captured.append((message.body, routing_key))

    payload = build_ingest_payload(9, "abc/a.txt", "a.txt", 1, "t", 4)
    asyncio.run(publish_to_exchange(FakeExchange(), payload))

    assert len(captured) == 1
    body, routing_key = captured[0]
    assert routing_key == INGEST_ROUTING_KEY
    assert json.loads(body.decode("utf-8")) == payload

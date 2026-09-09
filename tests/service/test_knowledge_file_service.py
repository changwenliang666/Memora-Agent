from datetime import datetime

from app.db.models.knowledge_file import KnowledgeFile
from app.service.knowledge_file_service import KnowledgeFileService
from app.service.rag_service import ImageOcrItem


def _row(**overrides) -> KnowledgeFile:
    values = {
        "user_id": 1,
        "filename": "notes.txt",
        "object_key": "abc/notes.txt",
        "content_type": "text/plain",
        "size": 12,
        "status": "pending",
        "image_keys": [],
        "ocr_results": [],
        "created_at": datetime(2026, 1, 1, 12, 0, 0),
        "updated_at": datetime(2026, 1, 1, 12, 0, 0),
    }
    values.update(overrides)
    return KnowledgeFile(**values)


def test_apply_processing_first_time_records_queue_wait() -> None:
    row = _row()
    now = datetime(2026, 1, 1, 12, 0, 5)

    assert KnowledgeFileService.apply_processing(row, now) == "run"
    assert row.status == "processing"
    assert row.started_at == now
    assert row.queue_wait_ms == 5000


def test_apply_processing_redeliver_keeps_started_at() -> None:
    started = datetime(2026, 1, 1, 12, 0, 5)
    row = _row(
        status="processing",
        started_at=started,
        queue_wait_ms=5000,
    )

    assert KnowledgeFileService.apply_processing(
        row, datetime(2026, 1, 1, 12, 1, 0)
    ) == "run"
    assert row.started_at == started
    assert row.queue_wait_ms == 5000
    assert row.status == "processing"


def test_apply_processing_skips_terminal_status() -> None:
    row = _row(status="done")
    assert KnowledgeFileService.apply_processing(row, datetime.now()) == "skip"
    row = _row(status="failed")
    assert KnowledgeFileService.apply_processing(row, datetime.now()) == "skip"


def test_apply_done_records_duration_and_bodies() -> None:
    started = datetime(2026, 1, 1, 12, 0, 5)
    row = _row(status="processing", started_at=started)
    now = datetime(2026, 1, 1, 12, 0, 8)

    KnowledgeFileService.apply_done(
        row,
        now,
        image_keys=["abc/images/a.png"],
        markdown=None,
        plain_text="hello",
        ocr_results=[ImageOcrItem(image_key="abc/notes.txt", text="ocr")],
    )

    assert row.status == "done"
    assert row.error_message is None
    assert row.finished_at == now
    assert row.duration_ms == 3000
    assert row.plain_text == "hello"
    assert row.image_keys == ["abc/images/a.png"]
    assert row.ocr_results == [{"image_key": "abc/notes.txt", "text": "ocr"}]


def test_apply_failed_records_public_error_and_duration() -> None:
    started = datetime(2026, 1, 1, 12, 0, 5)
    row = _row(status="processing", started_at=started)
    now = datetime(2026, 1, 1, 12, 0, 6)

    KnowledgeFileService.apply_failed(row, now, "建库失败")

    assert row.status == "failed"
    assert row.error_message == "建库失败"
    assert row.finished_at == now
    assert row.duration_ms == 1000

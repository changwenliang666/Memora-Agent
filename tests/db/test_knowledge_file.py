from sqlalchemy import JSON
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from app.db.models.knowledge_file import KnowledgeFile


def test_knowledge_file_columns() -> None:
    names = {column.name for column in KnowledgeFile.__table__.columns}
    assert KnowledgeFile.__tablename__ == "knowledge_files"
    assert names == {
        "id",
        "user_id",
        "filename",
        "object_key",
        "content_type",
        "size",
        "status",
        "error_message",
        "image_keys",
        "markdown",
        "plain_text",
        "ocr_results",
        "started_at",
        "finished_at",
        "queue_wait_ms",
        "duration_ms",
        "created_at",
        "updated_at",
    }
    assert "ocr_text" not in names
    assert KnowledgeFile.__table__.c.markdown.nullable is True
    assert KnowledgeFile.__table__.c.plain_text.nullable is True
    assert KnowledgeFile.__table__.c.ocr_results.nullable is False
    assert KnowledgeFile.__table__.c.image_keys.nullable is False
    assert KnowledgeFile.__table__.c.status.nullable is False
    assert KnowledgeFile.__table__.c.content_type.nullable is False
    assert KnowledgeFile.__table__.c.error_message.nullable is True
    assert KnowledgeFile.__table__.c.started_at.nullable is True
    assert KnowledgeFile.__table__.c.finished_at.nullable is True
    assert KnowledgeFile.__table__.c.queue_wait_ms.nullable is True
    assert KnowledgeFile.__table__.c.duration_ms.nullable is True
    for column_name in ("markdown", "plain_text"):
        column_type = KnowledgeFile.__table__.c[column_name].type
        assert isinstance(column_type, MEDIUMTEXT)
        assert type(column_type).__name__ == "MEDIUMTEXT"
    assert isinstance(KnowledgeFile.__table__.c.ocr_results.type, JSON)
    assert type(KnowledgeFile.__table__.c.ocr_results.type) is type(
        KnowledgeFile.__table__.c.image_keys.type
    )
    index_names = {index.name for index in KnowledgeFile.__table__.indexes}
    assert "ix_knowledge_files_user_created" in index_names


def test_knowledge_file_status_default_is_pending() -> None:
    assert KnowledgeFile.__table__.c.status.default.arg == "pending"
    assert KnowledgeFile.__table__.c.content_type.default.arg == ""

from sqlalchemy.dialects.mysql import MEDIUMTEXT

from memora_agent.db.models.knowledge_file import KnowledgeFile


def test_knowledge_file_columns() -> None:
    names = {column.name for column in KnowledgeFile.__table__.columns}
    assert KnowledgeFile.__tablename__ == "knowledge_files"
    assert names == {
        "id",
        "user_id",
        "filename",
        "object_key",
        "size",
        "image_keys",
        "markdown",
        "plain_text",
        "ocr_text",
        "created_at",
        "updated_at",
    }
    assert KnowledgeFile.__table__.c.markdown.nullable is True
    assert KnowledgeFile.__table__.c.plain_text.nullable is True
    assert KnowledgeFile.__table__.c.ocr_text.nullable is True
    assert KnowledgeFile.__table__.c.image_keys.nullable is False
    for column_name in ("markdown", "plain_text", "ocr_text"):
        column_type = KnowledgeFile.__table__.c[column_name].type
        assert isinstance(column_type, MEDIUMTEXT)
        assert type(column_type).__name__ == "MEDIUMTEXT"

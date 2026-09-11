from app.db.schema import (
    conversations_align_statements,
    knowledge_files_align_statements,
    messages_align_statements,
)

_CURRENT_COLUMNS = {
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


def test_align_statements_upgrade_ocr_text_and_body_types() -> None:
    statements = knowledge_files_align_statements(
        {"markdown", "plain_text", "ocr_text", "image_keys"}
    )
    joined = " ".join(statements)
    assert "MODIFY markdown MEDIUMTEXT NULL" in joined
    assert "MODIFY plain_text MEDIUMTEXT NULL" in joined
    assert "ADD COLUMN ocr_results JSON NOT NULL" in joined
    assert "DROP COLUMN ocr_text" in joined
    assert "MODIFY ocr_text" not in joined
    assert "ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'done'" in joined
    assert "ADD COLUMN content_type VARCHAR(128) NOT NULL DEFAULT ''" in joined


def test_align_statements_noop_when_already_current() -> None:
    statements = knowledge_files_align_statements(_CURRENT_COLUMNS)
    joined = " ".join(statements)
    assert "ADD COLUMN ocr_results" not in joined
    assert "DROP COLUMN ocr_text" not in joined
    assert "ADD COLUMN status" not in joined
    assert "ADD COLUMN content_type" not in joined
    assert "ADD COLUMN queue_wait_ms" not in joined
    assert "MODIFY markdown MEDIUMTEXT NULL" in joined
    assert "MODIFY plain_text MEDIUMTEXT NULL" in joined


def test_align_statements_adds_ocr_results_when_column_missing() -> None:
    statements = knowledge_files_align_statements({"id", "filename"})
    assert any("ADD COLUMN ocr_results JSON NOT NULL" in item for item in statements)
    assert not any("DROP COLUMN ocr_text" in item for item in statements)
    assert not any("MODIFY markdown" in item for item in statements)
    assert any("ADD COLUMN status" in item for item in statements)


def test_align_statements_adds_timing_columns_when_missing() -> None:
    statements = knowledge_files_align_statements(
        {"markdown", "plain_text", "ocr_results", "image_keys"}
    )
    joined = " ".join(statements)
    assert "ADD COLUMN started_at DATETIME NULL" in joined
    assert "ADD COLUMN finished_at DATETIME NULL" in joined
    assert "ADD COLUMN queue_wait_ms BIGINT NULL" in joined
    assert "ADD COLUMN duration_ms BIGINT NULL" in joined
    assert "ADD COLUMN error_message VARCHAR(512) NULL" in joined


def test_conversations_align_adds_missing_columns() -> None:
    statements = conversations_align_statements({"id", "user_id"})
    joined = " ".join(statements)
    assert "ADD COLUMN title VARCHAR(255) NOT NULL DEFAULT ''" in joined
    assert "ADD COLUMN message_count INT NOT NULL DEFAULT 0" in joined


def test_conversations_align_noop_when_current() -> None:
    statements = conversations_align_statements(
        {"id", "user_id", "title", "message_count", "created_at", "updated_at"}
    )
    assert statements == []


def test_messages_align_adds_missing_columns() -> None:
    statements = messages_align_statements({"id", "conversation_id"})
    joined = " ".join(statements)
    assert "ADD COLUMN seq INT NOT NULL DEFAULT 0" in joined
    assert "ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'user'" in joined
    assert "MODIFY content" not in joined


def test_messages_align_upgrades_content_type() -> None:
    statements = messages_align_statements(
        {"id", "conversation_id", "role", "content", "seq", "created_at"}
    )
    joined = " ".join(statements)
    assert "MODIFY content MEDIUMTEXT NOT NULL" in joined
    assert "ADD COLUMN seq" not in joined
    assert "ADD COLUMN role" not in joined

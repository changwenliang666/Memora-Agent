from app.db.schema import knowledge_files_align_statements


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


def test_align_statements_noop_when_already_current() -> None:
    statements = knowledge_files_align_statements(
        {"markdown", "plain_text", "ocr_results", "image_keys"}
    )
    joined = " ".join(statements)
    assert "ocr_results" not in joined or "ADD COLUMN ocr_results" not in joined
    assert "DROP COLUMN ocr_text" not in joined
    assert "MODIFY markdown MEDIUMTEXT NULL" in joined
    assert "MODIFY plain_text MEDIUMTEXT NULL" in joined


def test_align_statements_adds_ocr_results_when_column_missing() -> None:
    statements = knowledge_files_align_statements({"id", "filename"})
    assert any("ADD COLUMN ocr_results JSON NOT NULL" in item for item in statements)
    assert not any("DROP COLUMN ocr_text" in item for item in statements)
    assert not any("MODIFY markdown" in item for item in statements)

from sqlalchemy import inspect, text

_TABLE = "knowledge_files"


def knowledge_files_align_statements(columns: set[str]) -> list[str]:
    """按已有列算出要对 ``knowledge_files`` 执行的 ALTER。

    ``create_all`` 不会改已有表。旧库可能仍是 ``ocr_text`` + ``TEXT`` 正文列。
    """
    statements: list[str] = []
    if "markdown" in columns:
        statements.append(
            f"ALTER TABLE {_TABLE} MODIFY markdown MEDIUMTEXT NULL"
        )
    if "plain_text" in columns:
        statements.append(
            f"ALTER TABLE {_TABLE} MODIFY plain_text MEDIUMTEXT NULL"
        )
    if "ocr_results" not in columns:
        statements.append(
            f"ALTER TABLE {_TABLE} "
            "ADD COLUMN ocr_results JSON NOT NULL DEFAULT (JSON_ARRAY())"
        )
    if "ocr_text" in columns:
        statements.append(f"ALTER TABLE {_TABLE} DROP COLUMN ocr_text")
    return statements


def align_knowledge_files_schema(connection) -> None:
    """把已有 ``knowledge_files`` 对齐到当前模型。单条失败只打印，不阻断其余语句。"""
    inspector = inspect(connection)
    if _TABLE not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(_TABLE)}
    for statement in knowledge_files_align_statements(columns):
        try:
            connection.execute(text(statement))
        except Exception as exc:
            print(exc)

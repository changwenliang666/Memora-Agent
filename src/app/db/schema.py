from sqlalchemy import inspect, text

_TABLE = "knowledge_files"


def knowledge_files_align_statements(columns: set[str]) -> list[str]:
    """按已有列算出要对 ``knowledge_files`` 执行的 ALTER。

    ``create_all`` 不会改已有表。旧库可能仍是 ``ocr_text`` + ``TEXT`` 正文列，
    或缺少状态机 / 耗时列。已有成功行的 ``status`` 默认 ``done``。
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
    # 旧行都是「向量成功才插入」的成功记录，加列默认 done，不能默认 pending
    if "status" not in columns:
        statements.append(
            f"ALTER TABLE {_TABLE} "
            "ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'done'"
        )
    if "error_message" not in columns:
        statements.append(
            f"ALTER TABLE {_TABLE} ADD COLUMN error_message VARCHAR(512) NULL"
        )
    # 旧行没有存过 content_type，空串让列表仍能返回；新行 complete 会写入申报值
    if "content_type" not in columns:
        statements.append(
            f"ALTER TABLE {_TABLE} "
            "ADD COLUMN content_type VARCHAR(128) NOT NULL DEFAULT ''"
        )
    if "started_at" not in columns:
        statements.append(
            f"ALTER TABLE {_TABLE} ADD COLUMN started_at DATETIME NULL"
        )
    if "finished_at" not in columns:
        statements.append(
            f"ALTER TABLE {_TABLE} ADD COLUMN finished_at DATETIME NULL"
        )
    if "queue_wait_ms" not in columns:
        statements.append(
            f"ALTER TABLE {_TABLE} ADD COLUMN queue_wait_ms BIGINT NULL"
        )
    if "duration_ms" not in columns:
        statements.append(
            f"ALTER TABLE {_TABLE} ADD COLUMN duration_ms BIGINT NULL"
        )
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
    # create_all 不会给已有表补索引
    index_names = {index["name"] for index in inspector.get_indexes(_TABLE)}
    if "ix_knowledge_files_user_created" not in index_names:
        try:
            connection.execute(
                text(
                    "CREATE INDEX ix_knowledge_files_user_created "
                    "ON knowledge_files (user_id, created_at)"
                )
            )
        except Exception as exc:
            print(exc)

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from app.db.models.conversation import Conversation, Message


def test_conversation_columns() -> None:
    names = {column.name for column in Conversation.__table__.columns}
    assert Conversation.__tablename__ == "conversations"
    assert names == {
        "id",
        "user_id",
        "title",
        "message_count",
        "created_at",
        "updated_at",
    }
    index_names = {index.name for index in Conversation.__table__.indexes}
    assert "ix_conversations_user_updated" in index_names


def test_message_columns_and_seq_unique() -> None:
    names = {column.name for column in Message.__table__.columns}
    assert Message.__tablename__ == "messages"
    assert names == {
        "id",
        "conversation_id",
        "role",
        "content",
        "seq",
        "created_at",
    }
    assert isinstance(Message.__table__.c.content.type, MEDIUMTEXT)
    unique = [
        constraint
        for constraint in Message.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert any(
        set(constraint.columns.keys()) == {"conversation_id", "seq"}
        for constraint in unique
    )
    index_names = {index.name for index in Message.__table__.indexes}
    assert "ix_messages_conversation_seq" in index_names

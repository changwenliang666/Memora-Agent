import pytest
from pydantic import ValidationError

from memora_agent.schema.files import CompleteRequest, PresignRequest


def test_presign_request_requires_fields() -> None:
    with pytest.raises(ValidationError):
        PresignRequest.model_validate({"filename": "notes.pdf", "content_type": "application/pdf"})


def test_presign_request_rejects_empty_filename() -> None:
    with pytest.raises(ValidationError):
        PresignRequest(filename="", content_type="application/pdf", size=1024)


def test_complete_request_requires_object_key() -> None:
    with pytest.raises(ValidationError):
        CompleteRequest.model_validate(
            {
                "filename": "notes.pdf",
                "content_type": "application/pdf",
                "size": 1024,
            }
        )

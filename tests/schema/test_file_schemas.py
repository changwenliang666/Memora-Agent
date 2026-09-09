import pytest
from pydantic import ValidationError

from app.schema.files import CompleteRequest, FileInfo, PresignRequest


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


def test_file_info_requires_download_url() -> None:
    with pytest.raises(ValidationError):
        FileInfo.model_validate(
            {
                "object_key": "abc/notes.pdf",
                "filename": "notes.pdf",
                "content_type": "application/pdf",
                "size": 1024,
                "expires_in": 3600,
            }
        )


def test_file_info_requires_expires_in() -> None:
    with pytest.raises(ValidationError):
        FileInfo.model_validate(
            {
                "object_key": "abc/notes.pdf",
                "filename": "notes.pdf",
                "content_type": "application/pdf",
                "size": 1024,
                "download_url": "https://r2.example/download",
            }
        )


def test_file_info_keeps_declared_fields() -> None:
    info = FileInfo(
        object_key="abc/notes.pdf",
        filename="notes.pdf",
        content_type="application/pdf",
        size=1024,
        download_url="https://r2.example/download",
        expires_in=3600,
    )

    assert info.object_key == "abc/notes.pdf"
    assert info.filename == "notes.pdf"
    assert info.content_type == "application/pdf"
    assert info.size == 1024
    assert info.download_url == "https://r2.example/download"
    assert info.expires_in == 3600

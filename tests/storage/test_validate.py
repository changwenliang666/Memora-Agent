import pytest

from app.storage.validate import FileDeclarationError, validate_declaration


def test_valid_pdf_is_accepted() -> None:
    validate_declaration("notes.pdf", "application/pdf", 1_048_576)


def test_valid_markdown_plain_text_is_accepted() -> None:
    validate_declaration("readme.md", "text/plain", 2048)


def test_valid_markdown_markdown_type_is_accepted() -> None:
    validate_declaration("readme.md", "text/markdown", 2048)


def test_valid_txt_is_accepted() -> None:
    validate_declaration("notes.txt", "text/plain", 1)


def test_valid_png_is_accepted() -> None:
    validate_declaration("photo.png", "image/png", 1024)


def test_valid_jpeg_is_accepted() -> None:
    validate_declaration("photo.jpeg", "image/jpeg", 2048)


def test_valid_jpg_is_accepted() -> None:
    validate_declaration("photo.jpg", "image/jpeg", 2048)


def test_valid_docx_is_accepted() -> None:
    validate_declaration(
        "report.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        2048,
    )


def test_disallowed_extension_is_rejected() -> None:
    with pytest.raises(FileDeclarationError, match="仅支持"):
        validate_declaration("notes.exe", "application/octet-stream", 1024)


def test_content_type_mismatch_is_rejected() -> None:
    with pytest.raises(FileDeclarationError, match="不匹配"):
        validate_declaration("notes.pdf", "text/plain", 1024)


def test_zero_size_is_rejected() -> None:
    with pytest.raises(FileDeclarationError, match="size"):
        validate_declaration("empty.txt", "text/plain", 0)


def test_size_above_limit_is_rejected() -> None:
    with pytest.raises(FileDeclarationError, match="size"):
        validate_declaration("book.pdf", "application/pdf", 104_857_601)

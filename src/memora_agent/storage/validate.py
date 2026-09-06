from pathlib import Path

MAX_UPLOAD_SIZE = 104_857_600
ALLOWED_CONTENT_TYPES: dict[str, frozenset[str]] = {
    ".pdf": frozenset({"application/pdf"}),
    ".md": frozenset({"text/markdown", "text/plain"}),
    ".txt": frozenset({"text/plain"}),
}


class FileDeclarationError(ValueError):
    """前端申报的文件名、类型或大小不在白名单内。"""


def _normalized_content_type(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def validate_declaration(filename: str, content_type: str, size: int) -> None:
    """只检查调用方申报的三个字段，不读 R2、不打开本地文件。

    预签名 PUT 签完之后拦不住真实上传体积，本次按产品约定完全信任申报；
    这里的校验只是避免签发明显不该上传的地址。
    """
    suffix = Path(filename).suffix.lower()
    allowed_types = ALLOWED_CONTENT_TYPES.get(suffix)
    if allowed_types is None:
        raise FileDeclarationError("仅支持 .pdf、.md、.txt")

    normalized_type = _normalized_content_type(content_type)
    if normalized_type not in allowed_types:
        raise FileDeclarationError("content_type 与文件扩展名不匹配")

    if not isinstance(size, int) or isinstance(size, bool) or size < 1 or size > MAX_UPLOAD_SIZE:
        raise FileDeclarationError("size 必须是 1 到 104857600 之间的整数")

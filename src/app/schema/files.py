from datetime import datetime

from pydantic import BaseModel, Field


class PresignRequest(BaseModel):
    filename: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    size: int


class CompleteRequest(BaseModel):
    object_key: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    size: int


class FileInfo(BaseModel):
    """complete 响应：在原有下载信息上加上文件 id 和当前状态，方便前端立刻去轮询。"""

    id: int
    status: str
    object_key: str
    filename: str
    content_type: str
    size: int
    download_url: str
    expires_in: int


class FileSummary(BaseModel):
    """列表 / 详情摘要。不含 markdown 等正文列。"""

    id: int
    status: str
    error_message: str | None
    filename: str
    object_key: str
    content_type: str
    size: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    queue_wait_ms: int | None
    duration_ms: int | None


class FileListData(BaseModel):
    """列表分页：items 是当前页，total 是该用户全部条数，不受 limit/offset 影响。"""

    items: list[FileSummary]
    total: int


class PresignResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int

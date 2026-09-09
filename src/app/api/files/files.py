from fastapi import APIRouter, HTTPException, Query

from app.core.auth import get_current_user
from app.core.config import config
from app.db.models.knowledge_file import KnowledgeFile
from app.queue.ingest import build_ingest_payload, publish_ingest
from app.schema.files import (
    CompleteRequest,
    FileInfo,
    FileListData,
    FileSummary,
    PresignRequest,
    PresignResponse,
)
from app.schema.response import ResponseStructure
from app.service.knowledge_file_service import knowledgeFileService
from app.storage.r2 import R2ConfigError, R2Storage
from app.storage.validate import FileDeclarationError, validate_declaration

files_router = APIRouter(
    prefix="/files",
    tags=["files"],
)


def get_r2_storage() -> R2Storage:
    return R2Storage(config.r2)


def to_file_summary(row: KnowledgeFile) -> FileSummary:
    """列表 / 详情共用的摘要。故意不带 markdown / plain_text / ocr_results，
    轮询带 MEDIUMTEXT 会把接口打爆。
    """
    return FileSummary(
        id=row.id,
        status=row.status,
        error_message=row.error_message,
        filename=row.filename,
        object_key=row.object_key,
        content_type=row.content_type,
        size=row.size,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        queue_wait_ms=row.queue_wait_ms,
        duration_ms=row.duration_ms,
    )


@files_router.post("/presign", response_model=PresignResponse)
async def presign(request: PresignRequest) -> PresignResponse:
    """只签发临时上传地址，不接收文件。

    大文件走本服务会占带宽、容易超时，也会把 R2 密钥暴露面扩大到「整段上传」。
    浏览器拿 URL 直传 R2，本服务只负责白名单和签名。
    """
    try:
        validate_declaration(request.filename, request.content_type, request.size)
    except FileDeclarationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = get_r2_storage().presign_put(request.filename, request.content_type)
    except R2ConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return PresignResponse(
        upload_url=result.upload_url,
        object_key=result.object_key,
        expires_in=result.expires_in,
    )


@files_router.post("/complete", response_model=ResponseStructure[FileInfo])
async def complete(request: CompleteRequest):
    """上传完成：落 pending 行、入队，立刻返回。建库由 worker 跑，不在本请求里。

    这里签发的 download_url 只给前端预览。worker 必须自己再 presign_get，
    否则消息在队列里一待，这个 URL 就过期了。

    先插行再发消息。发失败就把这行标 failed 并 500，避免永远停在 pending。
    """
    try:
        result = get_r2_storage().presign_get(request.object_key)
    except R2ConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # BackgroundTasks 出了请求就读不到 ContextVar，入队前先把 user 抠出来
    user = get_current_user()
    record = await knowledgeFileService.create_pending(
        user_id=user.id,
        filename=request.filename,
        object_key=request.object_key,
        size=request.size,
        content_type=request.content_type,
    )
    try:
        await publish_ingest(
            build_ingest_payload(
                knowledge_file_id=record.id,
                object_key=request.object_key,
                filename=request.filename,
                user_id=user.id,
                username=user.username,
                size=request.size,
            )
        )
    except Exception as exc:
        await knowledgeFileService.mark_failed(record.id, "入队失败")
        raise HTTPException(status_code=500, detail="入队失败") from exc

    return ResponseStructure[FileInfo](
        message="文档正在处理中...",
        data=FileInfo(
            id=record.id,
            status=record.status,
            object_key=request.object_key,
            filename=request.filename,
            content_type=request.content_type,
            size=request.size,
            download_url=result.download_url,
            expires_in=result.expires_in,
        ),
    )


@files_router.get("", response_model=ResponseStructure[FileListData])
async def list_files(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """当前用户的文件列表，新的在前。data.total 是总数，data.items 是当前页。"""
    user = get_current_user()
    rows, total = await knowledgeFileService.list_for_user(user.id, limit, offset)
    return ResponseStructure[FileListData](
        message="查询成功",
        data=FileListData(
            items=[to_file_summary(row) for row in rows],
            total=total,
        ),
    )


@files_router.get("/{file_id}", response_model=ResponseStructure[FileSummary])
async def get_file(file_id: int):
    """按 id 查自己的文件状态，给前端轮询。别人的 id 与不存在都是 404，不暴露这条在不在。"""
    user = get_current_user()
    row = await knowledgeFileService.get_for_user(user.id, file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return ResponseStructure[FileSummary](
        message="查询成功",
        data=to_file_summary(row),
    )

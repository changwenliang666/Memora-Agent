from fastapi import APIRouter, HTTPException
from memora_agent.core.config import load_r2_config
from memora_agent.schema.files import (
    CompleteRequest,
    FileInfo,
    PresignRequest,
    PresignResponse,
)
from memora_agent.storage.r2 import R2ConfigError, R2Storage
from memora_agent.storage.validate import FileDeclarationError, validate_declaration
from memora_agent.service.rag_service import RagService
from fastapi import BackgroundTasks
from memora_agent.schema.response import ResponseStructure

files_router = APIRouter(
    prefix="/files",
    tags=["files"],
)


def get_r2_storage() -> R2Storage:
    return R2Storage(load_r2_config())


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
async def complete(request: CompleteRequest, background_tasks: BackgroundTasks):
    """按申报的 object_key 签发短时 GET，不读桶、不落库。

    download_url 可直接交给 MinerU loader。以后入库加在 return 之前即可。
    """
    try:
        result = get_r2_storage().presign_get(request.object_key)
    except R2ConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    background_tasks.add_task(
        RagService.build_knowledge_base,
        result.download_url,
        request.object_key,
        request.filename,
    )
    return ResponseStructure[FileInfo](
        message="文档正在处理中...",
        data = FileInfo(
            object_key=request.object_key,
            filename=request.filename,
            content_type=request.content_type,
            size=request.size,
            download_url=result.download_url,
            expires_in=result.expires_in,
        )
    )
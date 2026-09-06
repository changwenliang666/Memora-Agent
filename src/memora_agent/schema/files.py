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
    object_key: str
    filename: str
    content_type: str
    size: int


class PresignResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int

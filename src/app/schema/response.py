from pydantic import BaseModel, Field
from app.schema.bizcode import BizCode
from typing import TypeVar

T = TypeVar('T')

class ResponseStructure[T](BaseModel):
    code: int = Field(default=BizCode.SUCCESS.value)
    message: str
    data: T | None = None
    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "data": self.data,
        }

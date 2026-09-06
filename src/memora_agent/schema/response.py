from pydantic import BaseModel, Field
from memora_agent.schema.bizcode import BizCode
from typing import TypeVar

T = TypeVar('T')

class ResponseStructure[T](BaseModel):
    code: int = Field(default=BizCode.SUCCESS.value)
    message: str
    data: T
    def to_dict(self):
        return {
            "code": self.code.value,
            "message": self.message,
            "data": self.data,
        }
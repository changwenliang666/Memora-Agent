from pydantic import BaseModel

class OcrResult(BaseModel):
    text: str
from typing import Literal

from pydantic import BaseModel, Field

# 意图标签
IntentLabel = Literal["other", "history", "weather"]
# 意图置信度
IntentConfidence = Literal["high", "medium", "low"]

# 意图识别结果
class IntentResult(BaseModel):
    intent: IntentLabel = Field(
        default="other",
        description="用户这句话的主意图，只选一个",
    )
    confidence: IntentConfidence = Field(
        default="medium",
        description="意图识别的置信度",
    )
# 低置信度时，模型返回的固定回答

class LowConfidenceResponse(BaseModel):
    response: str = Field(
        default="对不起，我无法回答这个问题。",
        description="低置信度时，模型返回的固定回答",
    )


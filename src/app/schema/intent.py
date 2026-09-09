from typing import Literal

from pydantic import BaseModel, Field

# 意图标签
IntentLabel = Literal["other", "history", "weather", "summary", "regenerate", "help", "mood"]
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
    review_opinion: str | None = Field(
        default=None,
        description="复核模型的复核意见，未走复核时为空",
    )


class ReviewResult(BaseModel):
    intent: IntentLabel = Field(
        default="other",
        description="复核后的主意图，只选一个",
    )
    confidence: IntentConfidence = Field(
        default="medium",
        description="复核后的置信度",
    )
    review_opinion: str = Field(
        min_length=1,
        description="复核意见：说明为何维持或修改小模型判断",
    )
# 低置信度时，模型返回的固定回答

class LowConfidenceResponse(BaseModel):
    user_input: str = Field(
        default="",
        description="用户输入的问题",
    )
    response: str = Field(
        default="对不起，我无法回答这个问题。",
        description="低置信度时，模型返回的固定回答",
    )
    reason_code: Literal["unsupported", "ambiguous", "low_confidence", "multi_intent"] = Field(
        default="low_confidence",
        description="降级原因：不支持、需澄清、低置信度或多意图",
    )
    review_opinion: str | None = Field(
        default=None,
        description="复核模型的复核意见，未走复核时为空",
    )


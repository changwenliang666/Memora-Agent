from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate

from memora_agent.core.provider import LLMProvider
from memora_agent.schema.intent import IntentResult, LowConfidenceResponse
from memora_agent.intent_classify.few_shot import few_shot_examples

#意图识别，用来识别用户意图，防止用户输入模型不支持的能力
class IntentClassify:
    def __init__(self):
        self.small_model = LLMProvider().get_model("ollama", "qwen3.5:4b-mlx")
        example_prompt = ChatPromptTemplate.from_messages([
            ("human", "{input}"),
            ("ai", "{output}"),
        ])
        few_shot_prompt = FewShotChatMessagePromptTemplate(
            examples=few_shot_examples,
            example_prompt=example_prompt,
        )
        self.prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是用户意图分类助手。根据用户输入判断唯一主意图："
                "history=历史人物/事件，weather=天气，other=其他。"
                "只返回一个意图；一句话含多个主题时选最主要的那个，无法判断时用 other。"
                "置信度：意图明确用 high；能分出主意图但夹杂其他主题用 medium；"
                "指代不清、信息不足、或多个意图都说得通时用 low。",
            ),
            few_shot_prompt,
            ("human", "{input}"),
        ])
        self.classifier = self.small_model.with_structured_output(IntentResult)
    # 获取意图
    async def get_intent(self, message: str) -> IntentResult | LowConfidenceResponse:
        messages = self.prompt.format_messages(input=message)
        result = await self.classifier.ainvoke(messages)
        if result.intent == "other":
            return LowConfidenceResponse(response="对不起，我暂时无法回答这个问题。")
        else:
            if result.confidence == "low":
                return LowConfidenceResponse(response="对不起，我暂时无法回答这个问题。")
            elif result.confidence == "medium":
                return LowConfidenceResponse(response="请您详细的描述您遇到了什么问题，以便于我为您解答")
        return result


from langchain_core.messages import HumanMessage,SystemMessage
from memora_agent.core.provider import LLMProvider

class OcrService:
    def __init__(self):
        self.llm = LLMProvider().get_model("qwen", "qwen3.8-max")

    async def invoke(self, image_url: str) -> str:
        result = await self.llm.ainvoke([
            SystemMessage(content=
            """
                你是一个图片识别助手，请识别用户提供的图片中的文字,用精炼的语言总结图片中的文字，不要遗漏内容;
                遇到水印内容，需要去掉水印,只输出和图片有关的内容;
            """
            ),
            HumanMessage(content=[
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": "请识别总结图片中的文字,不要遗漏"},
            ]),
        ])
        return result.content
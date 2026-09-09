from langchain_core.messages import HumanMessage, SystemMessage

from app.core.provider import LLMProvider

_EXTRACT_SYSTEM = """
你是一个图片识别助手，请识别用户提供的图片中的文字,用精炼的语言总结图片中的文字，不要遗漏内容;
遇到水印内容，需要去掉水印,只输出和图片有关的内容;
"""

_FIGURE_SYSTEM = """
你是知识库配图识别助手。先判断这张图有没有独立的检索价值。
无检索价值（装饰线、图标、纯 Logo、空白、占位图、仅水印、页码图、页眉页脚）时，只输出 SKIP，不要解释。
有检索价值（正文扫描、表格、图表、流程图、架构图、界面截图、手写）时，用精炼语言写出可嵌入的内容，不要遗漏；去掉水印；不要包 JSON、不要解释。
"""


def figure_vision_text(raw: str | None) -> str | None:
    """把 Markdown 配图的视觉输出解析成 KEEP 文本或跳过。

    trim 后大小写不敏感地等于 ``SKIP``、空串或 None 视为跳过。
    ``SKIP`` 后面还有其它文字则当作 KEEP。
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.casefold() == "skip":
        return None
    return text


class OcrService:
    def __init__(self):
        self.llm = LLMProvider().get_model("qwen", "qwen3.8-max")

    async def invoke(self, image_url: str) -> str:
        """独立图片：只抽取可嵌入文本，不按装饰跳过。"""
        result = await self.llm.ainvoke(
            [
                SystemMessage(content=_EXTRACT_SYSTEM),
                HumanMessage(
                    content=[
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": "请识别总结图片中的文字,不要遗漏"},
                    ]
                ),
            ]
        )
        return result.content or ""

    async def invoke_markdown_figure(self, image_url: str) -> str | None:
        """Markdown 配图：无检索价值返回 None，有价值返回精炼文本。"""
        result = await self.llm.ainvoke(
            [
                SystemMessage(content=_FIGURE_SYSTEM),
                HumanMessage(
                    content=[
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {
                            "type": "text",
                            "text": "若无检索价值只输出 SKIP；否则输出可嵌入文本。",
                        },
                    ]
                ),
            ]
        )
        content = result.content
        if not isinstance(content, str):
            content = str(content) if content else ""
        return figure_vision_text(content)

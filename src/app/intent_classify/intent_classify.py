from textwrap import dedent

from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate

from app.core.provider import LLMProvider
from app.schema.intent import (
    IntentResult,
    LowConfidenceResponse,
    ReviewResult,
)
from app.intent_classify.few_shot import few_shot_examples, review_few_shot_examples

# 意图识别，用来识别用户意图，防止用户输入模型不支持的能力
class IntentClassify:
    def __init__(self):
        llm = LLMProvider()
        self.small_model = llm.get_model("ollama", "qwen3.5:2b")
        self.review_model = llm.get_model("ollama", "qwen3.5:4b-mlx")
        example_prompt = ChatPromptTemplate.from_messages([
            ("human", "{input}"),
            ("ai", "{output}"),
        ])
        few_shot_prompt = FewShotChatMessagePromptTemplate(
            examples=few_shot_examples,
            example_prompt=example_prompt,
        )
        review_example_prompt = ChatPromptTemplate.from_messages([
            (
                "human",
                "用户输入：{input}\n小模型判断：intent={intent}, confidence={confidence}",
            ),
            ("ai", "{output}"),
        ])
        review_few_shot_prompt = FewShotChatMessagePromptTemplate(
            examples=review_few_shot_examples,
            example_prompt=review_example_prompt,
        )
        self.prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                dedent("""
                    你是用户意图分类器。判断“用户希望系统做什么”，不要按某个关键词直接分类。

                    标签边界：
                    - summary：要求概括、提炼当前或之前的对话/文本。
                    - regenerate：要求重新回答、改写、补充上一轮回答，或因不满意要求再答。
                    - help：询问本系统是谁、能做什么、怎么使用；普通的“帮我做某事”不是 help。
                    - history：询问真实历史人物、历史事件或历史事实。历史书、历史题材、商品偏好不是 history。
                    - weather：查询现实地点当前或未来的天气、气温、降雨等。天气类书籍、比喻、历史事件中的风雨不是 weather。
                    - mood：主要目的在表达本人当前情绪或寻求情绪回应，例如“我很难过”“好无聊”。喜欢某类商品、表达偏好、评价或拒绝不是 mood。
                    - other：以上都不符合，包括推荐、购物、编程、时间、旅行、作品和偏好选择等不支持的请求。
                      其中 other/high 表示“需求明确但当前不支持”，other/low 表示“信息不足或指代不清，需要澄清”。

                    判定步骤：
                    1. 先找用户的主要诉求或言语行为，再匹配标签。
                    2. summary/regenerate 看用户要求的动作；help 只看系统能力咨询；history/weather 看实际查询对象；mood 看表达情绪是否为主要目的。
                    3. 同一句有多个主题时，选主要诉求；无法确定主要诉求时用 other。

                    置信度：
                    - high：标签边界清楚且信息足够；明确不受支持的请求也应为 other/high。
                    - medium：主要意图可确定，但还包含一个独立的次要诉求。
                    - low：指代不清或信息不足，无法可靠判断用户要做什么。
                """).strip(),
            ),
            few_shot_prompt,
            ("human", "{input}"),
        ])
        self.review_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                dedent("""
                    你是意图复核器。先独立判断用户希望系统做什么，再检查小模型结论；不能因候选标签或单个关键词产生锚定。

                    标签边界：
                    - summary：概括或提炼对话/文本。
                    - regenerate：重答、改写或补充上一轮回答。
                    - help：询问本系统身份、能力或用法；普通求助不属于 help。
                    - history：查询真实历史人物、事件或史实；历史书、题材和偏好不属于 history。
                    - weather：查询现实地点当前或未来天气；书籍、比喻和历史中的天气不属于 weather。
                    - mood：主要在表达本人当前情绪或寻求情绪回应；喜欢、讨厌、评价、拒绝和选择偏好不属于 mood。
                    - other：其余不受支持或意图明确但不属于上述标签的请求。

                    优先看主要诉求，不按“历史、天气、喜欢”等词直接分类。明确单一意图用 high；有独立次要诉求用 medium；指代不清或信息不足用 low。
                    对 other 的判定也要区分：需求明确但不支持用 high，指代不清或信息不足用 low。
                    你可以维持或修改 intent 和 confidence，并用 review_opinion 简要说明依据。
                """).strip(),
            ),
            review_few_shot_prompt,
            (
                "human",
                "用户输入：{input}\n小模型判断：intent={intent}, confidence={confidence}",
            ),
        ])
        self.classifier = self.small_model.with_structured_output(IntentResult)
        self.reviewer = self.review_model.with_structured_output(ReviewResult)

    async def get_intent(self, message: str) -> IntentResult | LowConfidenceResponse:
        messages = self.prompt.format_messages(input=message)
        result = await self.classifier.ainvoke(messages)
        if result.confidence in ("medium", "low"):
            review_messages = self.review_prompt.format_messages(
                input=message,
                intent=result.intent,
                confidence=result.confidence,
            )
            review = await self.reviewer.ainvoke(review_messages)
            result = IntentResult(
                intent=review.intent,
                confidence=review.confidence,
                review_opinion=review.review_opinion,
            )
        if result.intent == "other" and result.confidence == "high":
            return LowConfidenceResponse(
                user_input=message,
                response="您的问题,当前并不支持,请您重新提问。",
                reason_code="unsupported",
                review_opinion=result.review_opinion,
            )
        if result.intent == "other":
            return LowConfidenceResponse(
                user_input=message,
                response="对不起，我没有完全理解您的需求，请补充更具体的信息，例如您希望我查询、总结还是改写什么内容。",
                reason_code="ambiguous",
                review_opinion=result.review_opinion,
            )
        if result.confidence == "low":
            return LowConfidenceResponse(
                user_input=message,
                response="对不起，我暂时无法回答这个问题,请您描述更详细的问题,以便于我为您解答。",
                reason_code="low_confidence",
                review_opinion=result.review_opinion,
            )
        if result.confidence == "medium":
            return LowConfidenceResponse(
                user_input=message,
                response="请您详细的描述您遇到了什么问题，以便于我为您解答",
                reason_code="multi_intent",
                review_opinion=result.review_opinion,
            )
        return result

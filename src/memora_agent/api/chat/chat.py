from fastapi import APIRouter
from langchain_core.messages import HumanMessage,AIMessage

from memora_agent.schema.chat import ChatRequest
from memora_agent.tools.tools import Tools
from memora_agent.agent.agent import Agent
from memora_agent.schema.config import AgentConfig
from memora_agent.rule.rule import Rule
from memora_agent.intent_classify.intent_classify import IntentClassify

chat_router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


@chat_router.post("/stream")
async def chat(request: ChatRequest):
    # TODO: 使用 request 中的模型选择接入流式响应。
    # model_response_parts: list[str] = []

    # async def generate() -> AsyncIterator[str]:
    #     try:
    #         async for chunk in provider.astream(
    #             [HumanMessage(content=request.message)]
    #         ):
    #             if chunk.content:
    #                 content = str(chunk.content)
    #                 model_response_parts.append(content)
    #                 yield f"data: {json.dumps({'message': chunk.content}, ensure_ascii=False)}\n\n"
    #     except Exception as e:
    #         yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    #         return
    #     model_response_content = "".join(model_response_parts)
    #     print(model_response_content)
    #     yield "data: [DONE]\n\n"

    # return StreamingResponse(
    #     generate(),
    #     media_type="text/event-stream",
    #     headers={
    #         "Cache-Control": "no-cache",
    #         "X-Accel-Buffering": "no",
    #     },
    # )
    tools = Tools()
    return {"message": "hello world", "tools": tools.tools}

@chat_router.post("/agent")
async def agent(request: ChatRequest):
    try:
        if request.provider_type is None or request.model_name is None:
            return {"message": "error", "error": "需要提供 provider_type 和 model_name"}
        tools = Tools()
        agent = Agent(AgentConfig(
            provider_type=request.provider_type,
            model_name=request.model_name,
            tools=tools.get_all_tools(),
            history_messages=[
                HumanMessage("你好,我叫大伟,我是一个agent工程师"),
                AIMessage("好的,我记住了,有什么可以帮助您的"),
                HumanMessage("我喜欢用macbook air电脑来进行开发,真的很舒服,屏幕和键盘,触摸板,反馈都挺好的,续航很强"),
                AIMessage("好的,我记住了,有什么可以帮助您的"),
                HumanMessage("我今年26岁，出生在北方的男性,喜欢生活在南方,喜欢吃西瓜,喜欢看电影，喜欢打篮球,我曾经获得过内蒙古自治区乌兰察布市篮球比赛冠军"),
                AIMessage("好的,我记住了,有什么可以帮助您的"),
                HumanMessage("我大伟,就是喜欢写代码，每天至少写2小时，我热爱的语言是python,因为它语法简单,而且社区活跃,而且我是一个agent工程师,所以我会使用python来开发agent"),
                ],

            system_prompt="你是一个ai助手,根据用户的提问，简洁明了的回答用户的问题.",
            human_input_message=request.message,
            stream=False,
            max_round=10,
        ))
        print(agent.build_system_prompt)
        response = await agent.run_loop()
    except Exception as e:
        return {"message": "error", "error": str(e)}
    
    return {"message": "hello world", "agent": response}
@chat_router.post("/rule")
async def rule(request: ChatRequest):
    rule = Rule(request.message)
    return {"message": "hello world", "rule": rule.check_rule_validity(), "hit_category": rule.hit_category, "hit_topic": rule.hit_topic, "hit_intent": rule.hit_intent}

@chat_router.post("/intent")
async def intent(request: ChatRequest):
    intent = await IntentClassify().get_intent(request.message)
    return {"message": "hello world", "intent": intent}
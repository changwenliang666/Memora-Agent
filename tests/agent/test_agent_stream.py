"""Agent.run_stream 的单测，用假 chat 模型驱动 astream，不打真实 LLM。"""

import pytest
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk

from app.agent.agent import Agent
from app.schema.config import AgentConfig
from app.schema.tools import ToolsDictList


class FakeStreamModel:
    """按脚本返回一连串 AIMessageChunk。每轮 pop 一段脚本。"""

    def __init__(self, rounds: list[list[AIMessageChunk]]):
        self._rounds = rounds
        self.bound = self  # bind_tools 返回自身

    def bind_tools(self, tools):
        return self

    async def astream(self, messages):
        chunks = self._rounds.pop(0)
        for chunk in chunks:
            yield chunk


def _text_chunk(text: str) -> AIMessageChunk:
    return AIMessageChunk(content=text)


def _tool_call_chunk(name: str, args: dict, call_id: str) -> AIMessageChunk:
    return AIMessageChunk(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


def _make_agent(model, tools=None, max_round=5) -> Agent:
    agent = Agent.__new__(Agent)  # 绕过 __init__ 里的真实 LLMProvider
    agent.current_model = model
    agent.tools = tools or ToolsDictList(tools_prompt="", tools_list=[])
    agent.history_messages = []
    agent.system_prompt = "你是一个助手,用于测试流式循环"
    agent.human_input_message = "你好"
    agent.max_round = max_round
    agent.stream = True
    return agent


async def _collect(agent: Agent):
    return [event async for event in agent.run_stream()]


@pytest.mark.asyncio
async def test_plain_text_streams_deltas_then_completed():
    model = FakeStreamModel([[
        _text_chunk("根据"),
        _text_chunk("制度"),
        _text_chunk("，"),
    ]])
    agent = _make_agent(model)

    events = await _collect(agent)

    deltas = [e for e in events if e.event == "message.delta"]
    assert [e.data["content"] for e in deltas] == ["根据", "制度", "，"]
    assert events[-1].event == "message.completed"
    assert not any(e.event.startswith("tool") for e in events)


@pytest.mark.asyncio
async def test_empty_chunks_do_not_emit_delta():
    model = FakeStreamModel([[
        _text_chunk(""),
        _text_chunk("你好"),
        _text_chunk(""),
    ]])
    agent = _make_agent(model)

    events = await _collect(agent)
    deltas = [e.data["content"] for e in events if e.event == "message.delta"]
    assert deltas == ["你好"]


@pytest.mark.asyncio
async def test_tool_call_then_text_emits_no_tool_events(monkeypatch):
    executed = {}

    async def fake_execute(self, tool_name, tool_args):
        executed["name"] = tool_name
        return "深圳晴天20度"

    monkeypatch.setattr(Agent, "execute_tool", fake_execute)

    model = FakeStreamModel([
        [_tool_call_chunk("get_weather", {"city": "深圳"}, "call_1")],
        [_text_chunk("深圳今天晴")],
    ])
    agent = _make_agent(model)

    events = await _collect(agent)

    assert executed["name"] == "get_weather"
    assert not any("tool" in e.event for e in events)
    deltas = [e.data["content"] for e in events if e.event == "message.delta"]
    assert deltas == ["深圳今天晴"]
    assert events[-1].event == "message.completed"


@pytest.mark.asyncio
async def test_tool_call_chunks_not_sent_as_delta(monkeypatch):
    async def fake_execute(self, tool_name, tool_args):
        return "ok"

    monkeypatch.setattr(Agent, "execute_tool", fake_execute)

    model = FakeStreamModel([
        [_tool_call_chunk("get_weather", {"city": "x"}, "call_1")],
        [_text_chunk("答")],
    ])
    agent = _make_agent(model)

    events = await _collect(agent)
    delta_texts = [e.data["content"] for e in events if e.event == "message.delta"]
    assert all("get_weather" not in t and "city" not in t for t in delta_texts)


@pytest.mark.asyncio
async def test_model_error_after_start_emits_failed():
    class BoomModel(FakeStreamModel):
        async def astream(self, messages):
            yield _text_chunk("半截")
            raise RuntimeError("模型中断")

    agent = _make_agent(BoomModel([[]]))

    events = await _collect(agent)
    assert events[0].event == "message.delta"
    assert events[-1].event == "message.failed"
    assert not any(e.event == "message.completed" for e in events)


@pytest.mark.asyncio
async def test_tool_error_emits_failed(monkeypatch):
    async def boom_execute(self, tool_name, tool_args):
        raise RuntimeError("工具失败")

    monkeypatch.setattr(Agent, "execute_tool", boom_execute)

    model = FakeStreamModel([
        [_tool_call_chunk("get_weather", {"city": "x"}, "call_1")],
    ])
    agent = _make_agent(model)

    events = await _collect(agent)
    assert events[-1].event == "message.failed"


@pytest.mark.asyncio
async def test_max_round_exhausted_emits_failed(monkeypatch):
    async def fake_execute(self, tool_name, tool_args):
        return "ok"

    monkeypatch.setattr(Agent, "execute_tool", fake_execute)

    # 每轮都要调工具，永远不出最终文本
    model = FakeStreamModel([
        [_tool_call_chunk("get_weather", {"city": "x"}, f"call_{i}")]
        for i in range(3)
    ])
    agent = _make_agent(model, max_round=3)

    events = await _collect(agent)
    assert events[-1].event == "message.failed"
    assert not any(e.event == "message.completed" for e in events)

# Memora Agent

基于 **FastAPI + LangChain** 的轻量 Agent 服务：多模型接入、工具调用循环，通过 HTTP API 对外提供对话能力。

## 简介

当前实现是一个可配置的 ReAct 风格 Agent 循环：模型按需发起工具调用，服务端执行工具并把结果回填到对话中，直到模型给出最终回复或达到最大轮数。适合作为后续扩展（流式输出、图编排、更多工具）的底座。

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| API 服务 | FastAPI | HTTP 接口与 OpenAPI 文档 |
| Agent | 自研循环 + LangChain | `bind_tools` + `ainvoke` 工具调用 |
| 模型接入 | langchain-ollama / langchain-openai | 本地 Ollama 与 OpenAI 兼容 API（如 DeepSeek） |
| 配置 | pydantic-settings | 从 `.env` 读取模型提供商配置 |
| 运行时 | Python ≥ 3.14 | 见 `.python-version` |

## 特性

- **多模型提供商**：`ollama`（本地）与 `website_api`（OpenAI 兼容，当前配置为 DeepSeek）
- **工具调用循环**：最多 `max_round` 轮；同步 / 异步工具统一走 `ainvoke`
- **内置示例工具**：查询天气（模拟）、获取当前时间
- **服务化接入**：FastAPI 暴露 REST API

## 快速开始

```bash
git clone git@github.com:changwenliang666/Memora-Agent.git
cd Memora-Agent

# 安装依赖（推荐 uv；默认会安装 dev 组中的 uvicorn）
uv sync

# 配置环境变量
cp .example.env .env
# 按需填写 Ollama / DeepSeek 相关配置
```

在项目根目录创建 `.env`（若 `.example.env` 为空，可直接按下面模板写入）：

```env
# Ollama（本地）
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_NAME=qwen3.5:4b
OLLAMA_THINK=false
OLLAMA_TEMPERATURE=0.7

# OpenAI 兼容接口（当前用于 DeepSeek）
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_MODEL_NAME=deepseek-v4-flash
DEEPSEEK_THINK=false
DEEPSEEK_TEMPERATURE=0.7
```

使用本地 Ollama 时，需先启动 Ollama 并拉取对应模型。

```bash
uv run uvicorn memora_agent.main:app --reload
```

启动后访问：

- API：`http://127.0.0.1:8000`
- 交互式文档：`http://127.0.0.1:8000/docs`

### 调用 Agent

```bash
curl -X POST http://127.0.0.1:8000/chat/agent \
  -H "Content-Type: application/json" \
  -d '{"message": "现在几点了？"}'
```

请求体：

```json
{ "message": "用户问题，1～500 字" }
```

成功时返回类似：

```json
{ "message": "hello world", "agent": "模型最终回复" }
```

失败时返回：

```json
{ "message": "error", "error": "异常信息" }
```

## API

| 方法 | 路径 | 状态 | 说明 |
|------|------|------|------|
| `POST` | `/chat/agent` | 可用 | 运行 Agent 循环并返回最终回复；当前固定使用 `ollama` 提供商 |
| `POST` | `/chat/stream` | 占位 | 流式接口尚未接上，目前返回占位 JSON |

## 项目结构

```
Memora-Agent/
├── src/memora_agent/
│   ├── main.py                 # FastAPI 入口，挂载路由
│   ├── agent/
│   │   └── agent.py            # Agent：拼提示词、执行工具、循环推理
│   ├── api/
│   │   └── chat/
│   │       └── chat.py         # /chat 路由
│   ├── core/
│   │   ├── config.py           # 从 .env 加载提供商配置
│   │   └── provider.py         # LLMProvider：按类型构造 ChatOllama / ChatOpenAI
│   ├── schema/
│   │   ├── chat.py             # ChatRequest
│   │   ├── config.py           # ProviderConfig、AgentConfig
│   │   └── tools.py            # 工具列表与参数 Schema
│   └── tools/
│       └── tools.py            # 内置工具定义与注册
├── pyproject.toml
├── uv.lock
└── README.md
```

### 模块职责

| 模块 | 职责 |
|------|------|
| `agent.Agent` | 绑定工具、构建系统提示词、按 `tool_calls` 调用工具并回填历史 |
| `core.LLMProvider` | 根据 `provider_type` 返回对应 Chat 模型 |
| `core.LLMProviderConfig` | 读取 Ollama / DeepSeek 环境变量并组装 `ProviderConfig` |
| `tools.Tools` | 注册 `get_weather`、`get_current_time`，生成工具列表与提示文案 |

## Agent 循环

`Agent.run_loop` 的流程：

1. 用系统提示词（含工具说明、历史消息）和用户输入调用模型 `ainvoke`
2. 若返回 `tool_calls`：按名称查找工具，`await tool.ainvoke(args)`，把结果写入 `ToolMessage`
3. 若无工具调用：把 `AIMessage` 写入历史并返回最终文本
4. 每轮递减 `max_round`（默认 10），用尽则结束

`ainvoke` 同时覆盖同步与异步工具：异步工具直接 await，同步工具在线程池中执行。新增工具只需在 `tools.py` 用 `@tool` 装饰（`def` 或 `async def` 均可），并加入 `get_all_tools` 的 `tools_list`。

当前内置工具：

| 名称 | 说明 |
|------|------|
| `get_weather` | 按城市名返回模拟天气；未提供城市时提示补全 |
| `get_current_time` | 返回当前真实日期与时间 |

## 开发

```bash
uv sync --dev
uv run uvicorn memora_agent.main:app --reload
```

切换模型提供商时，修改 `AgentConfig.provider_type` 为 `"ollama"` 或 `"website_api"`（当前 `/chat/agent` 写死为 `ollama`）。

## License

待定。

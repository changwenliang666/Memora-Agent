# Memora Agent

基于 **FastAPI + LangChain** 的轻量 Agent 服务：多模型接入、工具调用循环，通过 HTTP API 对外提供对话能力。

## 简介

当前实现是一个可配置的 ReAct 风格 Agent 循环：先用规则和意图分类过滤用户输入，再由模型按需发起工具调用，服务端执行工具并把结果回填到对话中，直到给出最终回复或达到最大轮数。适合作为后续扩展（流式输出、图编排、记忆）的底座。

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| API 服务 | FastAPI | HTTP 接口与 OpenAPI 文档 |
| Agent | 自研循环 + LangChain | `bind_tools` + `ainvoke` 工具调用 |
| 模型接入 | langchain-ollama / langchain-openai | 本地 Ollama 与 OpenAI 兼容 API（如 DeepSeek） |
| 配置 | pydantic-settings + TOML | TOML 保存模型清单，`.env` 保存密钥 |
| 运行时 | Python ≥ 3.14 | 见 `.python-version` |

## 特性

- **多模型提供商**：`ollama`（本地）与 `openai`（OpenAI 兼容，当前配置为 DeepSeek），每个 Provider 可配置多个模型
- **规则校验**：按主题词 + 动作意图拦截不支持的问题
- **意图分类**：Few-shot 分类为 `history` / `weather` / `other`，低置信度时拒绝回答
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
# 按需填写在线模型的 API Key
```

模型清单位于 `config/models.toml`。Provider 保存连接信息，`models`
数组保存该 Provider 下可选的多个模型：

```toml
[providers.ollama]
base_url = "http://localhost:11434"
temperature = 0.7

[[providers.ollama.models]]
name = "qwen3.5:4b-mlx"

[providers.openai]
base_url = "https://api.deepseek.com"
api_key_env = "DEEPSEEK_API_KEY"

[[providers.openai.models]]
name = "deepseek-chat"
```

Provider 级的 `think` 和 `temperature` 是默认值，模型条目中的同名参数可覆盖它们。
在线密钥不写入 TOML，只在 `.env` 中配置：

```env
DEEPSEEK_API_KEY=sk-your-key
```

使用本地 Ollama 时，需先启动 Ollama 并拉取 TOML 中对应的模型。

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
  -d '{"message": "现在几点了？", "provider_type": "ollama", "model_name": "qwen3.5:4b-mlx"}'
```

请求体：

```json
{
  "message": "用户问题，1～500 字",
  "provider_type": "ollama",
  "model_name": "qwen3.5:4b-mlx"
}
```

`provider_type` 与 `model_name` 由调用方指定，对应 `config/models.toml` 中已配置的 Provider 和模型。

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
| `POST` | `/chat/agent` | 可用 | 运行 Agent 循环；可按 `provider_type + model_name` 选择模型 |
| `POST` | `/chat/rule` | 可用 | 规则校验：是否允许回答，以及命中的分类 / 主题 / 意图 |
| `POST` | `/chat/intent` | 可用 | 意图分类：`history` / `weather` / `other`，低置信度返回固定话术 |
| `POST` | `/chat/stream` | 占位 | 流式接口尚未接上，目前返回占位 JSON |

请求体统一为 `ChatRequest`：必填 `message`。`/chat/agent` 还需要 `provider_type` 和 `model_name`。

## 项目结构

```
Memora-Agent/
├── config/
│   └── models.toml                 # Provider 与模型清单
├── src/memora_agent/
│   ├── main.py                     # FastAPI 入口，挂载 /chat 路由
│   ├── agent/
│   │   └── agent.py                # Agent：拼提示词、执行工具、循环推理
│   ├── api/
│   │   └── chat/
│   │       └── chat.py             # /chat/agent、/rule、/intent、/stream
│   ├── core/
│   │   ├── config.py               # 加载并校验 TOML，从 .env 读取密钥
│   │   └── provider.py             # 按 provider_type + model_name 构造 Chat 模型
│   ├── intent_classify/
│   │   ├── intent_classify.py      # Few-shot 意图分类
│   │   └── few_shot.py             # 意图分类示例
│   ├── rule/
│   │   ├── rule.py                 # 主题词 + 动作意图规则
│   │   └── policy.py               # 拦截词表
│   ├── schema/
│   │   ├── chat.py                 # ChatRequest
│   │   ├── config.py               # 模型 / Provider / Agent 配置类型
│   │   ├── intent.py               # 意图识别结果
│   │   └── tools.py                # 工具列表与参数 Schema
│   ├── tools/
│   │   └── tools.py                # 内置工具定义与注册
│   ├── graph/                      # 预留：图编排
│   └── memory/                     # 预留：记忆
├── tests/
│   ├── core/                       # 配置加载与模型选择
│   └── rule/                       # 规则拦截
├── .example.env                    # 在线模型 API Key 模板
├── pyproject.toml
├── uv.lock
└── README.md
```

### 模块职责

| 模块 | 职责 |
|------|------|
| `api.chat` | 对外 HTTP 入口，把请求转给 Agent / Rule / IntentClassify |
| `agent.Agent` | 绑定工具、构建系统提示词、按 `tool_calls` 调用工具并回填历史 |
| `core.LLMProviderConfig` | 从 TOML 读取 Provider 和模型清单 |
| `core.LLMProvider` | 根据 `provider_type + model_name` 返回对应 Chat 模型 |
| `intent_classify.IntentClassify` | 用小模型做 Few-shot 意图分类，低置信度拒绝回答 |
| `rule.Rule` | 同时命中主题词和动作词时拦截输入 |
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
uv run pytest
```

新增模型时，只需在 `config/models.toml` 对应 Provider 下增加 `[[providers.<type>.models]]` 条目。
调用 `/chat/agent` 时传入 `"ollama"` 或 `"openai"` 以及对应模型名即可切换。

## License

待定。

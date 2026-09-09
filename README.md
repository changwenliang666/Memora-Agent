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
| 配置 | dotenv + TOML | `Config` 按服务加载 `.env`；TOML 只放模型清单 |
| 中间件 | Docker Compose | 开发用 MySQL / Redis / RabbitMQ / Qdrant，应用仍本机运行 |
| 运行时 | Python ≥ 3.14 | 见 `.python-version` |

## 特性

- **多模型提供商**：`ollama`（本地）、`deepseek` 与 `qwen`（均为 OpenAI 兼容协议），每个实例可配置多个模型
- **规则校验**：按主题词 + 动作意图拦截不支持的问题
- **意图分类**：Few-shot 分类为 `history` / `weather` / `other`，低置信度时拒绝回答
- **工具调用循环**：最多 `max_round` 轮；同步 / 异步工具统一走 `ainvoke`
- **内置示例工具**：查询天气（模拟）、获取当前时间
- **服务化接入**：FastAPI 暴露 REST API
- **统一配置**：一个 `Config` 类按 MySQL、Redis、R2、MinerU、JWT、LLM 分组加载
- **用户认证**：用户名密码注册 / 登录，签发 JWT；除登录注册与文档外接口需带 `Authorization: Bearer`
- **开发中间件**：`docker compose up -d` 只起 MySQL / Redis / RabbitMQ / Qdrant，不把 FastAPI 放进容器

## 快速开始

```bash
git clone git@github.com:changwenliang666/Memora-Agent.git
cd Memora-Agent

# 安装依赖（推荐 uv；默认会安装 dev 组中的 uvicorn）
uv sync

# 配置环境变量（模板含中间件、MinerU、R2、JWT、在线模型密钥）
cp .example.env .env
# 按需填写在线模型的 API Key、R2 / MinerU，并替换 JWT_SECRET

# 先起 MySQL / Redis / RabbitMQ / Qdrant（应用仍在本机跑）
docker compose up -d
```

运行时配置只走 `core.config.config`。`Config` 构造时只读取一次项目根 `.env`，再用进程环境覆盖同名值，然后通过 `load_mysql()`、`load_redis()`、`load_r2()`、`load_mineru()`、`load_jwt()`、`load_llm()` 等方法生成分组配置：

```python
from app.core.config import config

config.mysql.host
config.r2.bucket_name
config.mineru.api_key
config.jwt.secret
config.llm["ollama"]
```

模型清单在 `config/models.toml`。每个供应商一张表，表名是实例名，`type` 是客户端种类（`ollama` 或 `openai` 兼容协议）。`models` 是聊天模型名列表，`embed_models` 是向量模型名。`base_url` 按配置原样传给客户端。

```toml
[ollama]
type = "ollama"
base_url = "http://127.0.0.1:11434"
think = false
temperature = 0.7
models = ["qwen3.5:4b-mlx", "qwen3.5:2b"]
embed_models = ["mxbai-embed-large:latest"]

[deepseek]
type = "openai"
base_url = "https://api.deepseek.com"
api_key_env = "DEEPSEEK_API_KEY"
think = false
temperature = 0.7
models = ["deepseek-v4-flash", "deepseek-chat"]

[qwen]
type = "openai"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
api_key_env = "QWEN_API_KEY"
think = false
temperature = 0.7
models = ["qwen3.8-max"]
```

`think` 和 `temperature` 是供应商级默认值。在线密钥不写入 TOML，只在 `.env` 中配置：

```env
DEEPSEEK_API_KEY=sk-your-key
QWEN_API_KEY=sk-your-key
JWT_SECRET=dev-only-change-me-jwt-secret-min-32b
JWT_EXPIRE_MINUTES=10080
```

`JWT_SECRET` 用于签发和校验登录 token，生产环境必须换成足够长的随机值。`JWT_EXPIRE_MINUTES` 默认 10080（七天）。

使用本地 Ollama 时，需先启动 Ollama 并拉取 TOML 中对应的模型。

```bash
uv run uvicorn app.main:app --reload
```

启动后访问：

- API：`http://127.0.0.1:8000`
- 交互式文档：`http://127.0.0.1:8000/docs`（无需登录）

### 注册与登录

除 `/auth/register`、`/auth/login` 和文档外，所有接口都需要 `Authorization: Bearer <token>`。

注册和登录始终返回 `{ "code", "message", "data" }`。看 `code` 判断成败：`0` 成功，`1001` 用户名已存在，`1002` 用户名或密码错误。这两条接口的业务失败也是 HTTP 200，不要按 4xx 判断。没带 token 访问受保护接口仍是 HTTP 401。

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "dawei", "password": "secret12"}'

curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "dawei", "password": "secret12"}'
```

登录成功后 `data.token` 即为 JWT。后续请求带上：

```bash
curl -X POST http://127.0.0.1:8000/chat/agent \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
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
| `POST` | `/auth/register` | 可用 | 用户名 + 密码注册；无需 JWT |
| `POST` | `/auth/login` | 可用 | 用户名 + 密码登录，返回 JWT |
| `POST` | `/chat/agent` | 可用 | 运行 Agent 循环；需 Bearer JWT |
| `POST` | `/chat/rule` | 可用 | 规则校验；需 Bearer JWT |
| `POST` | `/chat/intent` | 可用 | 意图分类；需 Bearer JWT |
| `POST` | `/chat/stream` | 占位 | 流式接口尚未接上；需 Bearer JWT |
| `POST` | `/files/presign` | 可用 | 签发 R2 预签名 PUT；需 Bearer JWT |
| `POST` | `/files/complete` | 可用 | 签发短时 GET 并后台切文档；需 Bearer JWT |

请求体统一为 `ChatRequest`：必填 `message`。`/chat/agent` 还需要 `provider_type` 和 `model_name`。

文件直传的流程、预签名原理和 `.env` 填法见 [docs/r2-file-upload.md](docs/r2-file-upload.md)。

## 项目结构

```
Memora-Agent/
├── config/
│   └── models.toml                 # Provider 与模型清单
├── src/app/
│   ├── main.py                     # FastAPI 入口，挂载 /auth、/chat、/files，JWT 中间件
│   ├── agent/
│   │   └── agent.py                # Agent：拼提示词、执行工具、循环推理
│   ├── api/
│   │   ├── auth/
│   │   │   └── auth.py             # /auth/register、/auth/login
│   │   ├── chat/
│   │   │   └── chat.py             # /chat/agent、/rule、/intent、/stream
│   │   └── files/
│   │       └── files.py            # /files/presign、/files/complete
│   ├── core/
│   │   ├── config.py               # Config：按服务加载环境变量与 TOML
│   │   ├── auth.py                 # JWT 签发/验签、密码哈希、当前用户 ContextVar
│   │   ├── auth_middleware.py      # 除白名单外校验 Bearer
│   │   └── provider.py             # 按 provider_type + model_name 构造 Chat 模型
│   ├── intent_classify/
│   │   ├── intent_classify.py      # Few-shot 意图分类
│   │   └── few_shot.py             # 意图分类示例
│   ├── rule/
│   │   ├── rule.py                 # 主题词 + 动作意图规则
│   │   └── policy.py               # 拦截词表
│   ├── schema/
│   │   ├── auth.py                 # 注册 / 登录请求与响应
│   │   ├── chat.py                 # ChatRequest
│   │   ├── config.py               # 模型 / Provider / Agent 配置类型
│   │   ├── files.py                # 文件直传请求 / 响应
│   │   ├── intent.py               # 意图识别结果
│   │   ├── response.py             # 统一响应包装
│   │   ├── bizcode.py              # 业务状态码
│   │   └── tools.py                # 工具列表与参数 Schema
│   ├── service/
│   │   ├── user_service.py         # 用户创建与按用户名查询
│   │   └── rag_service.py          # 文档解析与切分（complete 后台任务）
│   ├── storage/
│   │   ├── r2.py                   # boto3 签发 R2 预签名 URL
│   │   └── validate.py             # 文件类型与大小白名单
│   ├── tools/
│   │   └── tools.py                # 内置工具定义与注册
│   ├── graph/                      # 预留：图编排
│   └── memory/                     # 预留：记忆
├── tests/
│   ├── api/                        # /auth、/files、CORS
│   ├── core/                       # 配置加载与模型选择
│   ├── schema/                     # 请求体校验
│   ├── storage/                    # R2 签发与文件申报校验
│   └── rule/                       # 规则拦截
├── docs/
│   └── r2-file-upload.md           # 文件直传教学文档
├── compose.yaml                    # 开发中间件：MySQL / Redis / RabbitMQ / Qdrant
├── .example.env                    # 全量环境占位（中间件 + 密钥）
├── pyproject.toml
├── uv.lock
└── README.md
```

### 模块职责

| 模块 | 职责 |
|------|------|
| `api.auth` | 注册、登录，签发 JWT |
| `api.chat` | 对外 HTTP 入口，把请求转给 Agent / Rule / IntentClassify |
| `api.files` | 签发 R2 临时上传 / 下载地址，complete 后触发后台切文档 |
| `core.auth` | JWT、密码哈希、请求级 `get_current_user()` |
| `service.RagService` | MinerU 拉文件并按标题 / 长度切分 |
| `storage` | 文件申报校验与 boto3 预签名 |
| `agent.Agent` | 绑定工具、构建系统提示词、按 `tool_calls` 调用工具并回填历史 |
| `core.config` | 单次读取环境，并按服务分组加载运行时配置与模型清单 |
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
docker compose up -d
uv run uvicorn app.main:app --reload
uv run pytest
```

新增聊天模型时，只需把名字加进 `config/models.toml` 对应供应商的 `models` 列表。
调用 `/chat/agent` 时传入 `"ollama"`、`"deepseek"` 或 `"qwen"` 以及对应模型名即可切换。

## License

待定。

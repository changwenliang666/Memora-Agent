## Why

`config/models.toml` 的顶层表名同时充当供应商身份和客户端类型。`[openai]` 里实际写的是 DeepSeek 的 `base_url` 和 `DEEPSEEK_API_KEY`，再接入同为 OpenAI 兼容协议的 Qwen 时没有第二张表可写，只能覆盖 DeepSeek 或硬编码。调用方现在无法按「实例名」同时保留 DeepSeek 和 Qwen。

## What Changes

- TOML 顶层键改为供应商实例名（`ollama`、`deepseek`、`qwen`），每张表增加必填 `type` 声明客户端种类（`ollama` 或 `openai`）
- **BREAKING**：在线目录键从 `openai` 改为 `deepseek`；HTTP / Agent 的 `provider_type` 表示目录实例名，不再表示客户端库名；原先传 `"openai"` 的请求必须改为 `"deepseek"`
- `LLMProvider` 按表上的 `type` 选择 `ChatOllama` 或 `ChatOpenAI`，而不是按表名分支；未知 `type` 失败
- 增加 `[qwen]`：OpenAI 兼容客户端、独立 `base_url` 与 `QWEN_API_KEY`，模型清单至少包含现有试用模型 `qwen3.8-max`
- `.example.env` 增加 `QWEN_API_KEY` 占位；密钥仍不写进 TOML
- Chat 请求的 `provider_type` 不再用封闭的 `Literal["ollama", "openai"]` 限制实例名，未知实例在构造客户端时失败

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `llm-provider`: 目录按实例名列出；构造客户端时用表上的 `type` 选择实现，同一 `openai` 类型可对应多张表
- `runtime-config`: 每张供应商表必须声明 `type`；在线目录可同时包含 DeepSeek 与 Qwen，并各自指向独立的密钥环境名

## Impact

- `config/models.toml`：`[openai]` 改名为 `[deepseek]` 并加 `type`；新增 `[qwen]`
- `.example.env`、`README.md`：补充 `QWEN_API_KEY` 与实例名用法
- `src/memora_agent/schema/config.py`：`ProviderConfig` 增加 `type`；HTTP / Agent 的 `provider_type` 改为目录实例名字符串
- `src/memora_agent/core/provider.py`：按 `provider.type` 分支，不再按表名等于 `openai` / `ollama`
- `src/memora_agent/schema/chat.py`、`api/chat/chat.py`：请求体仍用 `provider_type` 字段，语义改为目录键
- `tests/core/test_provider.py`、`tests/core/test_r2_config.py`、`tests/core/test_chat_schema.py`
- 不改 `paddleOcr_service.py`（本地试验脚本，不走 Provider）
- 不新增 LangChain 依赖；Qwen 复用 `ChatOpenAI`

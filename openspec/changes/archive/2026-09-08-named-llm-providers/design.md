## Context

现状与动机见 proposal.md。行为契约见 `specs/llm-provider/spec.md` 与 `specs/runtime-config/spec.md`。

当前 `LLMProvider.get_model` 用调用方传入的表名做 `if provider_type == "ollama"` / `"openai"` 分支。`ProviderType = Literal["ollama", "openai"]` 同时约束 HTTP 请求体和目录键，因此目录里只能有一张 OpenAI 兼容表，DeepSeek 只能占用 `[openai]`。

`paddleOcr_service.py` 已能用 `ChatOpenAI` 打通 Qwen 兼容接口，但不走目录。本次只把同样的客户端接到命名实例上。

## Goals / Non-Goals

**Goals:**

- 目录键是实例名，客户端种类是表上的 `type`
- 同一 `type = "openai"` 可同时存在 `deepseek` 与 `qwen`
- 新增同类供应商只改 TOML 和对应 `*_API_KEY`，不必改 `Literal` 和分支
- 无效 `type` 在加载目录时失败

**Non-Goals:**

- 不改 HTTP 字段名 `provider_type`，不改 `list_providers` / `get_model` / `get_embeddings` 入口
- 不把 `paddleOcr_service.py` 接到 Provider
- 不新增 LangChain 客户端，不为 Qwen 单独做 SDK
- 不增加 embedding 供应商，不为单模型覆盖 `think` / `temperature`
- 不把密钥写入 TOML

## Decisions

### 1. 表名是实例，`type` 是客户端

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

`type` 只允许 `ollama` 或 `openai`。`openai` 表示 OpenAI 兼容 HTTP（`ChatOpenAI`），不是 OpenAI 官方账号。`base_url` 原样传递；若实际走阿里云 MaaS 工作区，只改这一行，不改代码。

仓库提交 DashScope 兼容模式地址，因为那是公开文档中的兼容入口；工作区专属域名属于部署配置。

备选：继续用表名当类型，Qwen 模型塞进 `[openai]`。否决：一份 `base_url` / 一份密钥，DeepSeek 与 Qwen 无法共存。

备选：嵌套 `[providers.qwen]`。否决：刚扁平化过，再加一层没有收益。

### 2. `ProviderConfig.type` 在加载时校验

```python
ClientType = Literal["ollama", "openai"]

class ProviderConfig(BaseModel):
    type: ClientType
    base_url: str
    api_key_env: str | None = None
    ...
```

`load_llm()` 仍对每张顶层表 `model_validate`。缺 `type` 或非法值在构造 `Config` 时失败，错误信息带上表名。

原 `ProviderType = Literal["ollama", "openai"]` 不再用于 HTTP / `AgentConfig`。改名为 `ClientType`，只出现在 `ProviderConfig.type`。请求体与 `get_model` 第一个参数改为普通 `str`（目录实例名）。未知实例仍在 `_get_provider` 时报 `未配置 Provider`。

备选：把 `Literal["ollama", "deepseek", "qwen"]` 写进请求 schema。否决：每加一家供应商都要改代码，目录就失去意义。

备选：非法 `type` 留到 `get_model` 再失败。否决：启动时就能发现配错，比第一次聊天才爆更清楚。

### 3. 按表上的 `type` 选客户端

```
get_model(instance, name)
  provider = catalog[instance]
  if provider.type == "ollama": ChatOllama(...)
  if provider.type == "openai": ChatOpenAI(..., extra_body=thinking)
```

`deepseek` 和 `qwen` 走同一支，差别只来自该表的 `base_url`、`api_key_env`、`think`、`temperature`。`get_embeddings` 同样看 `provider.type`，目前只有 `ollama` 实现。

方法参数名保持 `provider_type`，语义改为实例名，避免同步改 Agent / HTTP 字段。

### 4. Qwen 密钥与模型清单

`.example.env` 增加 `QWEN_API_KEY=` 占位，与 `DEEPSEEK_API_KEY` 并列。清单先放 `qwen3.8-max`（当前试用模型）。以后加模型只改 TOML 数组。

## Risks / Trade-offs

- [调用方仍传 `"openai"`] → 明确失败（目录无此键）；README 与示例改为 `"deepseek"` / `"qwen"`
- [OpenAPI 不再枚举供应商名] → 接受；权威清单是 `list_providers()` 和 TOML
- [DashScope 与 MaaS 工作区 URL 不同] → `base_url` 可替换，不写死在代码里
- [加载时校验 `type` 使缺字段的 TOML 无法启动] → 接受；比运行期才发现更好

## Migration Plan

1. `ProviderConfig` 增加必填 `type`；HTTP / Agent 的 `provider_type` 改为 `str`
2. `get_model` / `get_embeddings` 按 `provider.type` 分支
3. `models.toml`：`[openai]` 改名为 `[deepseek]` 并写 `type`；新增 `[qwen]`
4. `.example.env`、README、测试夹具同步实例名与 `QWEN_API_KEY`
5. 回滚：还原 TOML 表名、`type` 字段和 `Literal["ollama", "openai"]`

## Open Questions

无。MaaS 工作区 URL 与额外 Qwen 模型名都只是 TOML 值，不改变方案。

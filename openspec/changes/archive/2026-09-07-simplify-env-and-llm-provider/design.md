## Context

现状见 proposal.md。第一次实现已经把模型 TOML 扁平化并拆开 chat / embedding，但配置层仍由模块函数、平铺属性、property 和可变全局单例组成。`env()` 每读取一个字段都可能再次解析 `.env`；R2 / MinerU 先存散字段再重新组装；测试需要调用 `reset_settings()` 清理全局状态。Compose 与 `.example.env` 的变量名已经对齐，本次不改这一层契约。

## Goals / Non-Goals

**Goals:**

- 一个 `Config` 类完整表达“加载环境，再加载每组配置”的流程
- `.env` 只解析一次，进程环境只合并一次
- MySQL、Redis、RabbitMQ、Qdrant、R2、MinerU、LLM 都通过同名 `load_*()` 方法构造
- 调用方通过分组属性读取配置，不使用散乱字段
- TOML 每个供应商一张扁平表，`models` / `embed_models` 为字符串数组
- `list_providers()`、`get_model(provider, name)`、`get_embeddings(provider, name)` 三个入口
- 测试显式构造 `Config(env_file=...)`，不依赖全局缓存清理

**Non-Goals:**

- 不改 `compose.yaml`、不改 `.example.env` 变量名、不把应用打进容器
- 不把模型清单搬进环境变量，也不把密钥写进 TOML
- 不保留按模型覆盖 `think` / `temperature`
- 不新增供应商类型，不改 HTTP 契约
- 不使用自动字段注入、元类、动态注册表或依赖注入框架

## Decisions

### 1. 单一 Config 类按顺序加载

`Config.__init__(env_file=ENV_FILE, models_file=MODELS_CONFIG_FILE)` 只做可顺序阅读的赋值：

```python
class Config:
    def __init__(self, env_file=ENV_FILE, models_file=MODELS_CONFIG_FILE):
        self.values = self.load_env(env_file)
        self.app_env = self.get("APP_ENV", "dev")
        self.mysql = self.load_mysql()
        self.redis = self.load_redis()
        self.rabbitmq = self.load_rabbitmq()
        self.qdrant = self.load_qdrant()
        self.r2 = self.load_r2()
        self.mineru = self.load_mineru()
        self.llm = self.load_llm(models_file)
```

`load_env()` 调用一次 `dotenv_values(env_file)`，再 `values.update(os.environ)`，因此进程环境覆盖文件。`get()` 只从 `self.values` 读取并处理空白；`get_int()` 只负责整数转换。

每个 `load_*()` 都只负责一个配置组。例如 `load_r2()` 明确列出五个 R2 环境名并返回 `R2Config`，`load_mineru()` 只返回 `MineruConfig`。不先创建 `r2_account_id` 等临时属性，也不使用 property 二次组装。

备选：模块级 `env()` / `env_int()`。否决：加载状态与读取方法分离，且会重复解析 dotenv。

备选：`get_settings()` + `_settings` + `reset_settings()`。否决：为简单配置引入隐藏全局生命周期，测试也必须知道缓存细节。

### 2. 配置数据类型与加载逻辑分离

`schema/config.py` 只放无加载行为的数据对象：

- `MysqlConfig`
- `RedisConfig`
- `RabbitMQConfig`
- `QdrantConfig`
- `R2Config`（保留 `endpoint_url` / `is_complete()`）
- `MineruConfig`
- `ProviderConfig`

`core/config.py` 只放路径常量、`Config` 类和生产实例 `config = Config()`。调用方直接使用 `config.r2`、`config.mineru`、`config.mysql.host`。测试需要不同环境时直接 `Config(env_file=tmp_path / ".env")`。

这里继续使用项目已有的 Pydantic `BaseModel` 定义数据对象，但不使用 `BaseSettings` 或自动环境映射；字段和值之间的对应关系全部写在 `load_*()` 中。

### 3. 扁平 TOML，供应商级 think / temperature

```toml
[ollama]
base_url = "http://127.0.0.1:11434"
think = false
temperature = 0.7
models = ["qwen3.5:4b-mlx", "qwen3.5:2b"]
embed_models = ["mxbai-embed-large:latest"]

[openai]
base_url = "https://api.deepseek.com"
api_key_env = "DEEPSEEK_API_KEY"
think = false
temperature = 0.7
models = ["deepseek-v4-flash", "deepseek-chat"]
```

`ProviderConfig.models` 改为 `list[str]`；删除 `ModelConfig`。`schema.config.ProviderType` 保留给 HTTP / `AgentConfig`。

在线密钥由 `LLMProvider` 调用同一 `Config.get(provider.api_key_env)` 获取，保证模型和密钥来自同一个已经加载的环境快照。

备选：Python 字典当清单。否决：改模型要动代码。

### 4. Provider 三个方法，不用注册表

```
list_providers() -> dict[str, list[str]]   # 只含 models
get_model(provider_type, model_name)       # 只查 models
get_embeddings(provider_type, model_name)  # 只查 embed_models
```

`get_model` 里 `if provider_type == "ollama"` / `"openai"` 两支。未知供应商或名称不在对应列表里，抛 `ValueError`，文案带上供应商和名称。

`embedding_service.py` 与 `/chat/test-embeddings` 改调 `get_embeddings`。

备选：一个 `get_model` 内部按名字猜 embedding。否决：返回类型撒谎，正是要拆掉的复杂度。

`LLMProvider` 构造时接收 `Config`，默认使用生产实例。测试传入自己构造的 `Config`，不 monkeypatch 全局环境读取函数。

## Risks / Trade-offs

- [丢失模型级 temperature] → 接受；现有差异很小，统一用供应商默认值
- [模块级生产实例在 import 时加载] → 缺失密钥保持可选，不阻止启动；测试从不使用该实例
- [TOML 顶层键从 `providers.ollama` 变成 `ollama`] → 一次性改仓库内文件和测试断言
- [配置文件变化需要重启进程] → 接受；配置本来就是启动时快照，不做热加载

## Migration Plan

1. 把配置数据对象集中到 `schema/config.py`
2. 用单一 `Config` 类替换模块函数、平铺字段和缓存函数
3. 调用方切换到 `config.<group>`，Provider 接收同一 `Config`
4. 测试改为显式构造 `Config`，覆盖单次合并、分组加载和进程环境优先级
5. 更新 README；回滚时还原配置类与调用方即可，`.env` / Compose 无需回滚

## Open Questions

无。

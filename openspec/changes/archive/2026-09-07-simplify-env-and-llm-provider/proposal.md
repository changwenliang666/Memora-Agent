## Why

当前实现虽然移除了 `BaseSettings`，但仍把 `env()`、`env_int()`、TOML 加载、R2 / MinerU 数据模型、二十多个平铺字段和全局缓存混在 `core/config.py`。一个配置值从哪里来、何时加载、属于哪个服务仍不直观，需要改成按配置分组、按加载步骤顺序阅读的结构。

## What Changes

- 用一个普通 `Config` 类封装全部加载过程：构造时只合并一次 `.env` 与进程环境，再调用清晰的 `load_mysql()`、`load_r2()`、`load_mineru()`、`load_llm()` 等方法
- 每类配置使用独立的数据对象，调用方从 `config.mysql`、`config.r2`、`config.mineru`、`config.llm` 直接读取，不再维护二十多个平铺属性
- 生产代码只导入一个 `config = Config()` 实例；测试直接创建指定环境文件的 `Config`，不再使用 `_settings`、`get_settings()`、`reset_settings()` 或 `global`
- `core/config.py` 只负责读取和组装；R2、MinerU、中间件和 Provider 的数据类型统一放在 `schema/config.py`
- `config/models.toml` 改为扁平表：每个供应商一段，`models` / `embed_models` 为字符串数组；不再按模型覆盖 `think` / `temperature`（**BREAKING** 对依赖模型级覆盖的调用方）
- `LLMProvider` 提供 `list_providers()`，`get_model(provider_type, model_name)` 只构造聊天模型；向量模型走 `get_embeddings`
- `.example.env` 与 `compose.yaml` 的变量名和共用关系不变；应用仍不进容器

## Capabilities

### New Capabilities
- `llm-provider`: 列出已配置供应商及其聊天模型；用供应商类型和模型名构造聊天客户端；向量模型与聊天模型分开构造

### Modified Capabilities
- `runtime-config`: 单次环境快照按服务分组提供中间件、密钥和模型清单；模型清单使用扁平 TOML 表

## Impact

- `src/memora_agent/core/config.py`：改为单一 `Config` 加载类和一个生产实例
- `src/memora_agent/schema/config.py`：集中定义 MySQL、Redis、RabbitMQ、Qdrant、R2、MinerU 和 Provider 配置对象
- `src/memora_agent/core/provider.py`：从同一个 `Config` 实例读取模型目录和密钥；拆分 embedding
- `config/models.toml`：扁平化；embedding 模型从聊天 `models` 挪到 `embed_models`
- `src/memora_agent/service/embedding_service.py`、`api/chat/chat.py`：改用 `get_embeddings`
- `src/memora_agent/api/files/files.py`、`service/rag_service.py`、`api/chat/chat.py`：直接读取分组配置
- `tests/core/test_r2_config.py`、`tests/core/test_provider.py`、`tests/conftest.py`：改为显式构造 `Config`
- `README.md`、`docs/r2-file-upload.md`：说明改为 dotenv + 扁平 TOML
- HTTP 路径与响应体不变；Compose 服务与端口不变

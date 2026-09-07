## Why

模型清单走 TOML 模块全局、R2 / MinerU 走手写 `get_secret()`，同一进程里两套读配置的思路，后面再加 MySQL / Redis / RabbitMQ 只会继续分叉。开发也需要这三个中间件，但不该现在就把 FastAPI 塞进容器。

## What Changes

- 用一个 `Settings` 入口收拢运行时配置：环境变量 / `.env` 提供密钥与中间件地址，`config/models.toml` 仍只放模型清单，但由同一入口加载
- 删除 `get_secret`、`load_r2_config`、`load_mineru_config` 以及 import 时的 `llm_provider_config`
- `.example.env` 补全中间件连接项和已在代码中使用的 `MINERU_API_KEY`
- 新增开发用 Compose，只启动 MySQL、Redis、RabbitMQ，并把端口映射到本机
- 去掉 Ollama `base_url` 里把 `localhost` 静默改成 `127.0.0.1` 的逻辑，URL 以配置为准
- 本次不把 FastAPI 打成镜像，也不写 Redis / MySQL / 队列的业务代码

## Capabilities

### New Capabilities
- `runtime-config`: 运行时配置只通过一个 Settings 入口读取；密钥与中间件地址来自环境，模型清单来自 TOML
- `dev-infra`: 仓库提供一份 Compose，开发时一条命令拉起 MySQL、Redis、RabbitMQ

### Modified Capabilities
- `file-upload`: R2 凭证仍来自环境占位、不进 TOML，但读取方式改为统一 Settings，不再经过 `get_secret()` / `load_r2_config()`

## Impact

- `src/memora_agent/core/config.py`：改为 `Settings` + `get_settings()`
- `src/memora_agent/core/provider.py`、`api/files/files.py`、`service/rag_service.py`、`api/chat/chat.py`：改为从 `get_settings()` 取配置
- `tests/core/test_r2_config.py`、`tests/core/test_provider.py`：跟着入口改
- `.example.env`、`docs/r2-file-upload.md`、`README.md`：补中间件变量并改掉旧读法说明
- 新增 `compose.yaml`（以及开发叠加文件，若需要）
- `pydantic-settings` 已在依赖中，按实际使用；不新增业务客户端（不为此次加 redis / sqlalchemy / 消费 aio-pika）
- **兼容**：HTTP API 路径与响应体不变。未填 R2 时 `presign` / `complete` 仍是服务端错误而不是 import 崩溃
- 本机若依赖「TOML 写 localhost、代码改成 127.0.0.1」的隐性行为，需把 TOML 写成实际要连的地址

## Why

开发栈已经用 Compose 拉起 MySQL、Redis 和 RabbitMQ，应用仍在宿主机连接；`qdrant-client` 已安装，但本机还没有可复用的 Qdrant 实例，后续 RAG 落库没有和其它中间件一致的入口。现在把它按同一套约定加进开发栈，避免每人各自起容器、地址和配置对不齐。

## What Changes

- 在现有 `compose.yaml` 中增加 Qdrant 服务，只绑定 localhost、使用命名卷、带健康检查；不把 FastAPI 放进容器
- 在 `.example.env` 和 `get_settings()` 快照中增加 Qdrant 连接占位（host / HTTP port），命名与 MySQL、Redis、RabbitMQ 同一套环境变量风格
- 更新 README 中开发中间件的说明，把 Qdrant 列入 `docker compose up -d` 拉起的服务
- 不在本变更中接入 RAG 写入 / 检索，不引入 API Key 或生产部署

## Capabilities

### New Capabilities

- 无。Qdrant 作为现有开发中间件与运行时配置的第四个同类服务接入，不单独开能力。

### Modified Capabilities

- `dev-infra`: Compose 开发栈从 MySQL / Redis / RabbitMQ 扩展为同时包含 Qdrant，仍只发布本机端口、持久化命名卷、并报告就绪
- `runtime-config`: 运行时快照和示例环境文件增加 Qdrant 连接字段，与其它中间件同一入口读取

## Impact

- `compose.yaml`：新增 `qdrant` 服务与 `qdrant_data` 卷
- `.example.env`、`src/memora_agent/core/config.py`、配置相关测试：增加 `QDRANT_HOST` / `QDRANT_PORT`
- `README.md`：开发中间件列表从三个服务改为四个
- `openspec/specs/dev-infra`、`openspec/specs/runtime-config`：需求从「三个中间件」改为包含 Qdrant
- `qdrant-client` 已在 `pyproject.toml` 中，本变更不再新增依赖
- 不改 chat / files API，不改 `RagService` 切分逻辑

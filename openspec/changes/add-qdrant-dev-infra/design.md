## Context

现有开发栈把 MySQL、Redis、RabbitMQ 写在根目录 `compose.yaml`：只绑定 `127.0.0.1`、命名卷、健康检查，应用仍在宿主机通过 `.env` + `get_settings()` 连接。`qdrant-client` 已在 `pyproject.toml`，但 Compose 与运行时快照都还没有 Qdrant。动机见 `proposal.md`；行为合同见本变更下的 `dev-infra` / `runtime-config` delta。

## Goals / Non-Goals

**Goals:**

- 用与现有三个服务相同的 Compose 约定接入 Qdrant，一条 `docker compose up -d` 即可
- 快照用同一套环境变量风格暴露 `QDRANT_HOST` / `QDRANT_PORT`，缺省即可连本机开发实例
- 健康检查不依赖官方镜像里不存在的 `curl` / `wget`

**Non-Goals:**

- 不在本变更里把 `RagService` 接到 Qdrant，不建 collection、不写向量
- 不启用 Qdrant API Key / TLS，不把 Qdrant 配成生产集群
- 不把应用进程放进 Compose

## Decisions

### 1. 写进现有 `compose.yaml`，不另开文件

与 MySQL / Redis / RabbitMQ 共用一份定义，避免开发者记第二套命令。备选是 `compose.qdrant.yaml`，会破坏「一条命令拉起全部中间件」。

### 2. 镜像钉官方 `qdrant/qdrant` 的 v1.16 线

与其它服务一样钉主版本（`mysql:8.4`、`redis:7-alpine`、`rabbitmq:4-management`），实现时选当前可用的 `v1.16.x` 补丁标签。不跟 `latest`，避免开发机静默漂移。备选 `v1.15` 也能被现有 `qdrant-client` 使用，但 v1.16 更接近当前稳定线。

### 3. 发布 HTTP 6333，同时发布 gRPC 6334；快照只记 HTTP

规格要求本机 `6333` 可达。官方镜像默认还听 `6334`（gRPC），按 RabbitMQ 同时发 AMQP + 管理口的做法一并绑定 `127.0.0.1:6334:6334`，方便日后 `qdrant-client` 走 gRPC。`Settings` 只增加 `qdrant_host` / `qdrant_port`（默认 `127.0.0.1` / `6333`），与其它中间件「一个 HOST + 一个 PORT」对齐，不在本变更引入 `QDRANT_GRPC_PORT`。

### 4. 无认证，命名卷挂 `/qdrant/storage`

本地 Qdrant 与 Redis 一样不设密码 / API Key。数据落在 named volume `qdrant_data` → `/qdrant/storage`（官方默认路径），不 bind-mount 到仓库。

### 5. 健康检查用本机 TCP 探测 6333

官方镜像不含 `curl` / `wget`。采用与「端口已接受连接」等价的 bash `/dev/tcp` 探测，间隔和重试贴近 Redis（约 5s / 10 次），`start_period` 给 10s。不另起 sidecar 做 HTTP `/readyz`。

### 6. 配置走现有 `get_settings()` 映射，不新建 loader

在 `Settings` 增加字段，`get_settings()` 从 `_merged_env()` 读 `QDRANT_HOST` / `QDRANT_PORT`，缺省回落到与 Compose 发布口一致的值。`.example.env` 增加这两行。已有本机 `.env` 即使没补这两项，也能靠代码默认连上。测试沿用 `tests/core/test_r2_config.py` 对中间件默认值的断言，并覆盖进程环境覆盖 dotenv。

## Risks / Trade-offs

- [官方镜像无 HTTP 客户端，TCP 探测不等于 `/readyz` 就绪] → 开发栈可接受；`start_period` 覆盖冷启动。若日后镜像自带探测命令，再换成 HTTP 检查，规格不需改。
- [只把 HTTP port 写入快照，gRPC 口仅 Compose 发布] → 当前无调用方；接入 RAG 时若要用 gRPC，再补环境变量，不阻塞本变更。
- [本机已占用 6333/6334] → 与其它中间件相同：改 `.env` 与 Compose 端口映射，或停掉冲突进程。
- [已有 `.env` 没有 Qdrant 行] → 代码默认值覆盖；示例文件补齐，README 提醒复制或手工追加。

## Migration Plan

1. 实现后执行 `docker compose up -d`，会拉取 Qdrant 镜像并创建 `qdrant_data`。
2. 已有 MySQL / Redis / RabbitMQ 卷不受影响。
3. 回滚：从 `compose.yaml` 去掉 `qdrant` 服务后 `docker compose up -d`；卷可保留，需要时再 `docker volume rm`。

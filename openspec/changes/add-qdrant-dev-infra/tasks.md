## 1. Compose 接入 Qdrant

- [x] 1.1 在现有 `compose.yaml` 增加 `qdrant` 服务：镜像钉 `qdrant/qdrant` 的 v1.16.x；`127.0.0.1:6333:6333` 与 `127.0.0.1:6334:6334`；named volume `qdrant_data` 挂到 `/qdrant/storage`；用 bash `/dev/tcp` 探测 6333 做 healthcheck（约 5s 间隔、10 次、`start_period` 10s）；不设 API Key、不加 app service。`docker compose config` 能解析且列出 `qdrant`
- [x] 1.2 执行 `docker compose up -d`，确认 `qdrant` 与原有三个服务均为 healthy，本机 `127.0.0.1:6333` 可访问 Qdrant HTTP；`docker compose ps` 没有应用容器

## 2. 运行时配置与示例环境

- [x] 2.1 在 `Settings` 增加 `qdrant_host` / `qdrant_port`（默认 `127.0.0.1` / `6333`），`get_settings()` 从 `_merged_env()` 读 `QDRANT_HOST` / `QDRANT_PORT`。用 REPL 或测试确认缺这两项时快照仍能构造且默认值正确
- [x] 2.2 在 `.example.env` 增加 `QDRANT_HOST` / `QDRANT_PORT` 占位，与 Compose 发布口一致，不含真实密钥。对照 `Settings` 确认每个环境名都有一行
- [x] 2.3 扩展 `tests/core/test_r2_config.py`：默认快照含 `qdrant_host == "127.0.0.1"` 与 `qdrant_port == 6333`；进程环境可覆盖 dotenv 中的 Qdrant 值。执行该文件确认通过

## 3. 文档与回归

- [x] 3.1 更新 `README.md` 中技术栈、特性、快速开始与目录说明，把开发中间件从「MySQL / Redis / RabbitMQ」改为同时包含 Qdrant。通读能对上 `compose.yaml` 与 `.example.env`
- [x] 3.2 执行 `uv run pytest`，确认全量测试通过，且没有改动 chat / files API 或 `RagService` 切分逻辑

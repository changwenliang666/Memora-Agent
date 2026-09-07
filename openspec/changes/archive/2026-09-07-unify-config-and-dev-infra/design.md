## Context

现状见 proposal.md。配置入口在 `core/config.py`：TOML 在 import 时加载成模块全局，R2 / MinerU 各有一个 `load_*`，底层共用手写 `get_secret()`。`pydantic-settings` 已在依赖中但未使用。调用方：`LLMProvider`、`files.py`、`RagService`、`chat.py` 的 `/test-mineru`。仓库没有 Docker 文件。开发仍用本机 `uv run uvicorn`，Ollama 在宿主机。

## Goals / Non-Goals

**Goals:**

- 一个 `Settings` + `get_settings()`：环境映射只构建一次，typed 字段和 `api_key(name)` 都读这张表；TOML 在同一次构造里载入
- Compose 只跑三个中间件，端口映射给本机应用
- `.example.env` 成为环境名的唯一清单，Compose 与应用共用这些名字

**Non-Goals:**

- 不写 FastAPI Dockerfile / `compose.prod.yaml` / 应用 service
- 不引入 redis、SQLAlchemy、aio-pika 业务调用
- 不把模型清单搬进环境变量，也不把密钥写进 TOML
- 不改 `/files` 与 `/chat` 的 HTTP 契约（除缺 R2 时仍 500）
- 不清理 `/chat/test-mineru` 这类调试接口（只改它的配置读取）

## Decisions

### 1. 一个 Settings，两份文件

```
get_settings()
  |
  +-- 进程环境 覆盖  项目根 .env     --> 密钥 / 中间件 / APP_ENV
  +-- config/models.toml              --> settings.llm
```

`Settings` 用已有的 `pydantic-settings.BaseSettings`。`env_file` 指向项目根 `.env`，`extra="ignore"`。空字符串在字段校验里收成 `None`（与现在 `_env_value` 一致）。

`get_settings()` 用 `lru_cache`。测试 `cache_clear()` 后注入环境。不再保留 `load_r2_config` / `load_mineru_config` / `get_secret` / 模块级 `llm_provider_config`。

`R2Config` / `MineruConfig` 可以留成 Settings 上的属性或薄包装，避免 `R2Storage` 改构造签名；包装必须从同一 snapshot 取字段，不能再读环境。

备选：继续加 `load_mysql_config()`。否决：这正是本次要拆掉的分叉。

备选：模型清单也改成环境变量。否决：嵌套 provider / 多模型用 TOML 更合适，密钥与清单分离仍然正确。

### 2. 环境名与 Settings 字段

| 环境名 | 开发默认（写在 `.example.env`） |
|--------|--------------------------------|
| `APP_ENV` | `dev` |
| `MYSQL_HOST` | `127.0.0.1` |
| `MYSQL_PORT` | `3306` |
| `MYSQL_USER` | `memora` |
| `MYSQL_PASSWORD` | 开发占位，非空 |
| `MYSQL_DATABASE` | `memora` |
| `MYSQL_ROOT_PASSWORD` | 仅给 Compose 初始化，应用不读 |
| `REDIS_HOST` | `127.0.0.1` |
| `REDIS_PORT` | `6379` |
| `REDIS_PASSWORD` | 空（开发无密码） |
| `RABBITMQ_HOST` | `127.0.0.1` |
| `RABBITMQ_PORT` | `5672` |
| `RABBITMQ_USER` | `memora` |
| `RABBITMQ_PASSWORD` | 开发占位，非空 |
| `R2_*` / `MINERU_API_KEY` / `DEEPSEEK_API_KEY` | 保持现有名字，空占位 |

TOML 里的 `api_key_env` 仍是环境变量名。`Settings.api_key(name)` 从**同一张**已合并的环境映射取值，不另开 `os.getenv` 通道。新增在线密钥时：`.example.env` 加占位，TOML 写对应名字，不必再写一个 `load_*`。

以后应用进容器，只改 `MYSQL_HOST=mysql` 等主机名，字段名不变。

### 3. 去掉 localhost 改写

`provider.py` 不再 `.replace("localhost", "127.0.0.1")`。`config/models.toml` 的 ollama `base_url` 改成 `http://127.0.0.1:11434`，本机行为与现在实际连上的地址一致。测试里对改写的断言改为「配置是什么客户端就是什么」。

备选：保留改写并加 Docker 特例。否决：静默改 URL 会在容器里把「宿主机 Ollama」和「容器自己」搞混。

### 4. 一份 `compose.yaml`，只服务开发中间件

服务：`mysql`（`mysql:8.4`）、`redis`（`redis:7-alpine`）、`rabbitmq`（`rabbitmq:4-management`，开发需要管理台）。

- 端口：`3306`、`6379`、`5672`、`15672`
- 环境：Compose 插值 `${MYSQL_*}` / `${RABBITMQ_*}`，与应用同一 `.env`
- Redis 开发不加 `--requirepass`
- 三个 named volume，不 bind-mount 到仓库
- 各服务 healthcheck；不设 `app` service，因此也不需要 `depends_on` 到应用
- Redis AOF 打开，满足「重启不丢开发数据」

不在本次加 `compose.dev.yaml` / `compose.prod.yaml`：还没有应用容器，叠加文件没有第二套差异可叠。

日常：

```bash
docker compose up -d
uv run uvicorn memora_agent.main:app --reload
```

### 5. 文档与调用方切换

| 调用方 | 改为 |
|--------|------|
| `LLMProvider` | `get_settings().llm`，密钥 `settings.api_key(...)` |
| `get_r2_storage` | `R2Config` 从 snapshot 填 |
| `RagService` / `/test-mineru` | `settings.mineru` |
| `docs/r2-file-upload.md`、README | 写 `get_settings()`，补中间件与 MinerU 占位 |

`chat.py` 里未使用的 `dotenv` 导入随这次删掉。

## Risks / Trade-offs

- [本机仍写 `localhost` 的 TOML] → 部分栈上 IPv6 解析可能失败；默认 TOML 改为 `127.0.0.1`，并在 README 写明
- [`.env` 同时给 Compose 和应用] → 改密码要同时重启中间件；接受，避免两份环境文件
- [开发 Redis 无密码] → 端口只绑本机即可接受；生产另开 change
- [Compose 健康但应用尚未连库] → 本次没有客户端，风险只在「人以为已经接入」；README 写清「只起中间件」
- [lru_cache 测漏清缓存] → 测试夹具统一 `get_settings.cache_clear()`

## Migration Plan

1. 合并 Settings 与测试，确认现有 `/files`、provider 单测仍过
2. 补 `.example.env`；已有本地 `.env` 的人按模板追加中间件项
3. 提交 `compose.yaml`；开发者装 Docker Desktop 后 `docker compose up -d`
4. 回滚：删 compose、还原 `core/config.py` 即可；volume 需手动 `docker compose down -v`

## Open Questions

无。应用何时进容器、生产是否自建中间件，不影响本次任务拆分。

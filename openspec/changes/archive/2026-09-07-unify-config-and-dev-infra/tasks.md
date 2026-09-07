## 1. 统一 Settings 入口

- [x] 1.1 在 `core/config.py` 用 `pydantic-settings` 实现 `Settings` 与带缓存的 `get_settings()`：合并进程环境与项目根 `.env`，空值收成 `None`，同一次构造加载 `config/models.toml` 到 `llm`；提供 `api_key(name)` 读同一张环境映射。删除 `get_secret`、`load_r2_config`、`load_mineru_config` 和模块级 `llm_provider_config`。用 REPL 或测试确认缺 R2 / MinerU 时 import 不崩溃
- [x] 1.2 改写 `tests/core/test_r2_config.py`（及必要的 Settings 新测）：覆盖进程环境优先于 `.env`、空白当成缺失、完整 R2 仍能拼 endpoint、模型清单从 TOML 读出当前 ollama / openai 模型名。执行这些用例确认通过
- [x] 1.3 把 `LLMProvider`、`files.py`、`RagService`、`chat.py` 改为只从 `get_settings()` 取配置；去掉 `chat.py` 未使用的 `dotenv` 导入。`R2Storage` 仍收 `R2Config`，字段从 snapshot 填。执行 `uv run pytest tests/core tests/api/test_files.py tests/storage/test_r2.py` 确认通过

## 2. Provider URL 与环境模板

- [x] 2.1 删除 `provider.py` 对 ollama `base_url` 的 `localhost` → `127.0.0.1` 改写；把 `config/models.toml` 的 ollama 地址改成 `http://127.0.0.1:11434`；更新 `tests/core/test_provider.py` 为「配置是什么客户端就是什么」。执行该文件确认通过
- [x] 2.2 更新 `.example.env`：补上 design 表中的 `APP_ENV`、MySQL / Redis / RabbitMQ 项、`MINERU_API_KEY`，保留现有 R2 与 DeepSeek 占位且不含真实密钥。对照 `Settings` 字段确认每个环境名都有一行

## 3. 开发中间件 Compose

- [x] 3.1 新增 `compose.yaml`：`mysql:8.4`、`redis:7-alpine`、`rabbitmq:4-management`；映射 3306 / 6379 / 5672 / 15672；账号密码与库名插值自 `.env`；三个 named volume；各服务 healthcheck；无 app service。`docker compose config` 能解析
- [x] 3.2 用本地 `.env`（或从 example 拷一份填开发占位）执行 `docker compose up -d`，确认三个服务 healthy，且本机 `127.0.0.1` 对应端口可连；`docker compose ps` 没有应用容器

## 4. 文档与回归

- [x] 4.1 更新 `docs/r2-file-upload.md` 与 `README.md`：配置改为 `get_settings()`；写明 `.example.env` 全量占位；补充「先 `docker compose up -d` 再本机 uvicorn」以及模型 URL 不再改写。通读能对上 `core/config.py` 与 `compose.yaml`
- [x] 4.2 执行 `uv run pytest`，确认全量测试通过且没有残留对 `get_secret` / `load_r2_config` / `load_mineru_config` 的引用（测试夹具除外）

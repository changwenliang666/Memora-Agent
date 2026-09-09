## Why

仓库根目录已经叫 Memora-Agent，Python 源码包再叫 `memora_agent` 会让路径和 import 读起来像同一层东西。把 `src/memora_agent` 改成 `src/app`，让源码根更短、也和发行名分开。

## What Changes

- 把 `src/memora_agent/` 整包改名为 `src/app/`。
- **BREAKING**：所有 Python import、pytest `monkeypatch` 目标字符串从 `memora_agent` 改为 `app`。`from memora_agent.main import app` 变为 `from app.main import app`。
- **BREAKING**：启动命令从 `uv run uvicorn memora_agent.main:app` 改为 `uv run uvicorn app.main:app`。
- 在 `pyproject.toml` 声明 `[tool.uv.build-backend] module-name = "app"`。发行名仍是 `memora-agent`，和目录名不再一致，不写这项 `uv_build` 会继续找 `src/memora_agent`。
- 更新仍在维护的文档：`README.md`、`docs/r2-file-upload.md` 里的路径、import 和 uvicorn 命令。
- 不改 HTTP 路由、鉴权、CORS、入库、配置加载或 Compose 中间件。
- 不改 `pyproject.toml` 的 `[project].name`、FastAPI `title`、环境变量名、数据库名。
- 不改写 `openspec/changes/archive/` 里已经归档的历史记录。

## Capabilities

无规格变更。现有 `openspec/specs/` 都不把 Python 包名写成需求；HTTP 与运行时行为不变。本变更在 `.openspec.yaml` 设置了 `skip_specs: true`。

### New Capabilities

- 无。

### Modified Capabilities

- 无。

## Impact

- 源码：`src/memora_agent/` 下全部模块的相对位置不变，只换顶层包名；内部 `from memora_agent...` 一并改。
- 测试：`tests/` 里的 import 和 `monkeypatch.setattr("memora_agent....")` 字符串。
- 构建：`pyproject.toml` 增加 `module-name = "app"`，之后需要 `uv sync` 才能按新包名安装。
- 文档：`README.md`、`docs/r2-file-upload.md`。
- 运行中的开发进程：当前 `uvicorn memora_agent.main:app --reload` 在改名后会失效，必须改启动命令。
- 已归档 OpenSpec 变更、仓库名、Compose 服务名不受影响。

## 1. 目录与构建配置

- [x] 1.1 用 `git mv src/memora_agent src/app` 移动源码包，确认 `src/app/__init__.py` 与 `src/app/main.py` 存在，且 `src/memora_agent/` 已不存在
- [x] 1.2 在 `pyproject.toml` 增加 `[tool.uv.build-backend]` 且 `module-name = "app"`，确认 `[project].name` 仍是 `memora-agent`

## 2. 代码与测试引用

- [x] 2.1 把 `src/app/` 内所有 `memora_agent` import 改为 `app`，确认包内没有 `from memora_agent` / `import memora_agent`
- [x] 2.2 把 `tests/` 内所有 `memora_agent` import 与 `monkeypatch.setattr("memora_agent....")` 字符串改为 `app`，确认测试目录没有残留 `memora_agent`

## 3. 文档

- [x] 3.1 更新 `README.md`：import 示例、项目结构树、两处 `uvicorn memora_agent.main:app` 改为 `app` / `src/app/` / `uvicorn app.main:app`；确认文档里不再出现 `memora_agent`，且仍保留发行名 `memora-agent`
- [x] 3.2 更新 `docs/r2-file-upload.md` 的源码路径、进程表述和 uvicorn 命令，确认该文件不再出现 `memora_agent`

## 4. 同步与回归

- [x] 4.1 执行 `uv sync`，再用 `uv run python -c "from app.main import app"` 确认新包可导入
- [x] 4.2 执行 `uv run pytest`，确认全量测试通过；再搜索 `src/`、`tests/`、`README.md`、`docs/`，确认没有残留 `memora_agent`，且 `openspec/changes/archive/` 未被改动

## Context

当前源码在 `src/memora_agent/`，内部与测试一律 `import memora_agent...`。`pyproject.toml` 的发行名是 `memora-agent`；`uv_build` 默认把发行名规范化成模块目录 `src/memora_agent/`，仓库里没有 `[tool.uv.build-backend]`。FastAPI 实例在 `main.py` 里叫 `app`，启动入口是 `memora_agent.main:app`。动机见 proposal.md。

## Goals / Non-Goals

**Goals:**

- 顶层可导入模块变成 `app`，磁盘路径变成 `src/app/`。
- 可编辑安装、pytest、uvicorn 都走新模块名，不留下活代码对 `memora_agent` 的引用。
- 发行名继续叫 `memora-agent`，避免把 PyPI / uv 项目名和源码目录绑死。

**Non-Goals:**

- 不改 FastAPI 实例变量名（仍叫 `app`）。
- 不改 HTTP 路由、鉴权、CORS、入库、配置或 Compose。
- 不改写 `openspec/changes/archive/`。
- 不把 `__init__.py` 里 `hello()` 的发行名文案改成包名。

## Decisions

### 1. 发行名与模块名拆开，显式写 `module-name`

`[project].name` 保持 `memora-agent`。增加：

```toml
[tool.uv.build-backend]
module-name = "app"
```

`uv_build` 默认找 `src/<规范化发行名>/`，不写这项会继续要求 `src/memora_agent/`，改名后构建失败。

备选：把发行名也改成 `app`。否决——发行名表示产品，`app` 太泛，也不是这次要解的重名问题。

### 2. 先 `git mv` 再机械替换标识符

顺序：

1. `git mv src/memora_agent src/app`
2. 在 `src/app/`、`tests/`、`README.md`、`docs/r2-file-upload.md` 把标识符 `memora_agent` 换成 `app`（含 `from` / `import` 和 pytest `monkeypatch.setattr("memora_agent....")` 字符串）
3. 写入 `module-name = "app"`
4. `uv sync`，让可编辑安装指向新目录
5. `uv run pytest`

不要手拷目录。不要全局替换 `memora-agent`（发行名、`hello()` 返回值、FastAPI `title` 都保留）。

备选：只改目录、保留 `import memora_agent`。否决——用户要引用一起改；且 `uv_build` 的模块名就是目录名。

### 3. FastAPI 实例仍叫 `app`，启动目标变成 `app.main:app`

包名 `app` 和实例名 `app` 叠在一起，uvicorn 目标读起来像绕口令，但这是 FastAPI 的常见写法，且用户指定了包名 `app`。测试里 `from app.main import app` 同样成立。

备选：把实例改成 `application` / `api`。否决——超出「改包名」范围，会多动所有 `TestClient(app)`。

### 4. 活文档要改，归档变更不改

`README.md` 的树、import 示例、两处 uvicorn 命令要改。`docs/r2-file-upload.md` 的路径、`memora_agent` 进程表述、uvicorn 命令要改。`openspec/changes/archive/` 是当时的记录，保持原样。当前未归档变更里没有 `memora_agent` 路径，不必改。

## Risks / Trade-offs

- [改名后未 `uv sync`] → 环境仍指向旧路径，import 失败。任务里把 `uv sync` 放在 pytest 之前。
- [正在跑的 `--reload` 仍用旧模块] → 目录搬走后进程报错。文档改命令；实现时停掉旧 uvicorn 再启新的。
- [漏改 `monkeypatch` 字符串] → 测试静默打到错误对象。全量 `uv run pytest`；再用搜索确认 `src/`、`tests/`、`README.md`、`docs/` 没有残留 `memora_agent`。
- [包名 `app` 太泛，和实例名撞车] → 接受。启动命令写成 `app.main:app` 并在 README 写清楚。

## Migration Plan

1. 停掉本机 `uvicorn memora_agent.main:app`。
2. 按 Decisions 的顺序改目录、引用、`pyproject.toml`。
3. `uv sync && uv run pytest`。
4. 用 `uv run uvicorn app.main:app --reload` 重新启动。

回滚：把目录移回 `src/memora_agent`，还原 import 与去掉 `module-name`，再 `uv sync`。

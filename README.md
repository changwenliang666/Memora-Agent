# Memora Agent

基于 **FastAPI + LangChain + LangGraph** 开发的通用 Agent 平台。

## 简介

Memora Agent 提供可扩展的智能体编排与服务能力：用 LangGraph 管理多步推理与工具调用，用 LangChain 接入模型与生态组件，用 FastAPI 对外暴露稳定的 HTTP API。适合作为各类业务场景的 Agent 底座，快速接入对话、工具执行与工作流编排。

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| API 服务 | FastAPI | 异步 HTTP 接口、文档与中间件 |
| Agent 编排 | LangGraph | 状态图、多步推理、条件分支 |
| LLM / 工具 | LangChain | 模型接入、Prompt、工具调用 |
| 运行时 | Python ≥ 3.14 | 项目最低语言版本 |

## 特性

- **通用 Agent 能力**：对话、工具调用、多步工作流
- **图编排**：基于 LangGraph 的状态机与可观测执行路径
- **服务化接入**：FastAPI 提供 REST API，便于前端与业务系统集成
- **可扩展**：支持自定义工具、模型与图节点

## 快速开始

```bash
# 克隆仓库
git clone <repository-url>
cd Memora-Agent

# 安装依赖（推荐使用 uv）
uv sync

# 启动服务
uv run uvicorn memora_agent.main:app --reload
```

启动后访问：

- API：`http://127.0.0.1:8000`
- 交互式文档：`http://127.0.0.1:8000/docs`

## 项目结构

```
Memora-Agent/
├── src/memora_agent/    # 核心包
├── pyproject.toml       # 项目配置与依赖
└── README.md
```

## 开发

```bash
uv sync --dev
```

## License

待定。

# DevMind — SDD 驱动的多智能体软件开发助手

## 项目简介

DevMind 是一个基于 LangGraph 的多智能体 AI 系统，运用 SDD（规格驱动开发）方法论，实现从**自然语言需求 → 规格文档 → 代码生成 → 代码审查 → 测试验证**的全自动化软件开发闭环。

用户只需用自然语言描述需求，四个专业 AI Agent 即可协作完成完整的软件工程流程。

## 方向

**方向一：Agentic AI 原生开发**

## 技术栈

- **AI IDE**: Trae CN
- **LLM**: DeepSeek API (`deepseek-chat`)
- **Agent 框架**: LangGraph + LangChain
- **协议**: MCP (Model Context Protocol)
- **Memory**: ChromaDB (向量数据库) + 对话窗口
- **可观测性**: LangFuse (Tracing & LLMOps)
- **Web UI**: Streamlit
- **容器**: Docker + Docker Compose
- **语言**: Python 3.12

## 目录结构

```
cs599-project/
├── docs/                        # 项目文档
│   ├── product_spec.md          # 产品规格文档
│   ├── architecture_spec.md     # 架构规格文档
│   ├── api_spec.md              # API 规格文档
│   └── CS599_大作业报告.pdf      # 最终提交报告
├── src/                         # 项目源代码
│   ├── agents/                  # AI Agent 实现
│   │   ├── orchestrator.py      # LangGraph 工作流编排器
│   │   ├── spec_architect.py    # 规格架构师 Agent
│   │   ├── developer.py         # 开发者 Agent
│   │   ├── reviewer.py          # 代码审查 Agent
│   │   └── qa.py                # QA 测试 Agent
│   ├── tools/                   # Agent 工具集
│   │   ├── file_tools.py        # 文件操作工具
│   │   └── shell_tools.py       # 安全代码执行工具
│   ├── mcp/                     # MCP 协议服务
│   │   └── tool_server.py       # MCP Tool Server
│   ├── memory/                  # 记忆系统
│   │   ├── short_term.py        # 短期记忆（对话窗口）
│   │   └── long_term.py         # 长期记忆（ChromaDB）
│   ├── state/                   # 状态管理
│   │   └── workflow_state.py    # LangGraph 状态定义
│   ├── config/                  # 配置管理
│   │   ├── settings.py          # 环境变量配置
│   │   └── llm_config.py        # LLM 客户端配置
│   ├── evaluation/              # 评估与可观测性
│   │   ├── benchmark.py         # 代码质量评估
│   │   └── tracing.py           # LangFuse 追踪
│   ├── main.py                  # CLI 入口
│   └── app.py                   # Streamlit Web UI
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE                      # MIT License
└── README.md
```

## 环境搭建

### 1. 依赖安装

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/cs599-project.git
cd cs599-project

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 环境变量配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 DeepSeek API Key
# DEEPSEEK_API_KEY=sk-your-actual-key-here
```

⚠️ **严禁在代码中硬编码 API Key**，所有密钥通过 `.env` 文件注入。

### 3. 启动步骤

**方式一：Streamlit Web UI（推荐）**
```bash
streamlit run src/app.py
# 浏览器访问 http://localhost:8501
```

**方式二：命令行**
```bash
python src/main.py
# 按提示输入需求描述，输入 END 结束
```

**方式三：Docker**
```bash
docker compose up -d
# 浏览器访问 http://localhost:8501
```

## 项目状态

- [x] Proposal
- [x] MVP
- [x] Final

## 核心技术要素覆盖

| # | 要素 | 实现 |
|---|------|------|
| 1 | SDD 规格驱动开发 | Spec Architect 产出 Product/Architecture/API Spec，驱动后续所有 Agent |
| 2 | 工具使用 / Function Calling / MCP | 文件操作、代码执行工具 + MCP 协议 Tool Server |
| 3 | 记忆机制 | 短期：对话窗口滑动记忆；长期：ChromaDB 向量数据库 |
| 4 | 状态管理与多步骤推理 | LangGraph StateGraph + ReAct 循环 + 条件路由 |
| 5 | 多智能体协作 | 4 个专业 Agent 协作，Orchestrator 统一编排 |
| 6 | 可观测性与评估 | LangFuse Tracing + CodeBenchmark 代码质量评估 |

## 致谢

- 课程：CS599 企业级应用软件设计与开发
- 指导教师：戚欣
- 框架参考：LangGraph, LangChain, AutoGen

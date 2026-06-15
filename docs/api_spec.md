# API 规格文档 — API Spec

## 一、Orchestrator 接口

### 入口函数

```python
def run_workflow(
    requirement: str,
    project_context: str = "",
    target_language: str = "python"
) -> AgentState
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| requirement | str | 是 | 自然语言需求描述 |
| project_context | str | 否 | 项目附加上下文 |
| target_language | str | 否 | 目标编程语言，默认 python |

| 返回值 | 类型 | 说明 |
|--------|------|------|
| result | AgentState | 包含所有阶段输出的完整状态 |

---

## 二、Agent 输入/输出契约

### 2.1 Spec Architect Agent

**输入**（从 AgentState 读取）：
```python
{
    "requirement": str,          # 用户原始需求
    "project_context": str,      # 项目上下文
    "target_language": str,      # 目标语言
    "spec_revision_count": int,  # 修订次数
}
```

**输出**（合并回 AgentState）：
```python
{
    "product_spec": str | None,       # 产品规格（Markdown）
    "architecture_spec": str | None,  # 架构规格（Markdown）
    "api_spec": str | None,           # API 规格（Markdown）
    "spec_revision_count": int,       # 递增的修订计数
    "messages": [Message],            # 日志消息
}
```

### 2.2 Developer Agent

**输入**（从 AgentState 读取）：
```python
{
    "product_spec": str,
    "architecture_spec": str,
    "api_spec": str,
    "target_language": str,
    "review_result": ReviewResult | None,  # 审查反馈（修复时）
    "test_result": TestResult | None,      # 测试反馈（修复时）
    "coding_iteration": int,
}
```

**输出**：
```python
{
    "generated_files": [FileOp],  # 生成的文件列表
    "coding_iteration": int,      # 递增的迭代计数
    "messages": [Message],
}
```

### 2.3 Reviewer Agent

**输入**：
```python
{
    "product_spec": str,
    "generated_files": [FileOp],  # 待审查的代码文件
}
```

**输出**：
```python
{
    "review_result": ReviewResult,  # {score, passed, issues, suggestions}
    "review_iteration": int,
    "messages": [Message],
}
```

### 2.4 QA Agent

**输入**：
```python
{
    "product_spec": str,
    "generated_files": [FileOp],  # 待测试的代码文件
}
```

**输出**：
```python
{
    "test_result": TestResult,  # {total, passed, failed, details, coverage}
    "test_iteration": int,
    "generated_files": [FileOp],  # 追加测试文件
    "messages": [Message],
}
```

---

## 三、核心数据类型

### AgentState（LangGraph 共享状态）
```python
class AgentState(TypedDict):
    phase: WorkflowPhase                    # 当前阶段
    messages: Sequence[Message]             # 消息历史
    requirement: str                        # 用户需求
    project_context: str                    # 项目上下文
    target_language: str                    # 目标语言

    # Spec 阶段
    product_spec: str | None
    architecture_spec: str | None
    api_spec: str | None
    spec_revision_count: int

    # 开发阶段
    generated_files: Sequence[FileOp]
    coding_iteration: int

    # 审查阶段
    review_result: ReviewResult | None
    review_iteration: int

    # 测试阶段
    test_result: TestResult | None
    test_iteration: int

    # 控制
    max_iterations: int
    error_message: str | None
    final_report: str | None
```

### 子类型
```python
class FileOp(TypedDict):
    path: str      # 文件路径
    content: str   # 文件内容
    action: str    # "create" | "update" | "delete"

class ReviewResult(TypedDict):
    score: int            # 0-100
    passed: bool          # 是否通过
    issues: list[str]     # 发现的问题
    suggestions: list[str]  # 改进建议

class TestResult(TypedDict):
    total: int            # 测试总数
    passed: int           # 通过数
    failed: int           # 失败数
    details: list[str]    # 详细输出
    coverage: float       # 覆盖率估算
```

---

## 四、工具函数签名

### 文件工具（file_tools.py）
```python
@tool
def read_file(path: str) -> str
    """读取文件内容。path: 相对于工作目录的文件路径。"""

@tool
def write_file(path: str, content: str) -> str
    """写入文件。path: 文件路径。content: 文件内容。"""

@tool
def list_directory(path: str = ".") -> str
    """列出目录内容。path: 目录路径，默认为当前目录。"""
```

### Shell 工具（shell_tools.py）
```python
@tool
def execute_code(code: str, language: str = "python") -> str
    """在沙箱中执行代码。code: 源代码。language: 语言类型。超时 30 秒。"""
```

---

## 五、MCP 协议接口

### Tool Server 端点（tool_server.py）

MCP Tool Server 通过标准 MCP 协议暴露以下工具：

| 工具名称 | 描述 | 参数 |
|----------|------|------|
| `read_file` | 读取文件 | `path: string` |
| `write_file` | 写入文件 | `path: string`, `content: string` |
| `list_directory` | 列出目录 | `path: string?` |
| `execute_code` | 执行代码 | `code: string`, `language: string?` |

**启动方式**：
```bash
python -m src.mcp.tool_server
```

---

## 六、LLM 调用规范

### 请求格式（DeepSeek API / OpenAI 兼容）
```python
client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "<系统提示词>"},
        {"role": "user", "content": "<用户提示词>"},
    ],
    temperature=0.1,   # 代码生成用低温度
    max_tokens=4096,
)
```

### 响应解析
- 优先从 ````json``` 代码块中提取 JSON
- 解析失败时降级为纯文本处理
- 所有 Agent 的超时时间为 60 秒

---

## 七、错误处理约定

| 场景 | 处理策略 |
|------|----------|
| LLM API 调用失败 | 捕获异常，记录 error_message，路由到 handle_error |
| JSON 解析失败 | 降级到纯文本提取，记录警告 |
| 测试执行超时 | 30 秒超时，标记为失败，继续流程 |
| 最大迭代次数耗尽 | 跳过当前阶段，继续后续流程 |
| 文件写入权限不足 | 捕获 OSError，报告具体错误路径 |

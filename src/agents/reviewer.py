"""Reviewer Agent — reviews generated code for quality, security, and correctness."""

from src.config.llm_config import create_llm_client, get_model_name
from src.state.workflow_state import AgentState, ReviewResult


SYSTEM_PROMPT = """你是一位严格的代码审查员（Code Reviewer）。你的职责是审查代码质量。

审查维度：
1. **正确性**：代码是否符合规格文档的要求
2. **安全性**：是否存在安全漏洞（SQL注入、XSS、路径遍历、硬编码密钥等）
3. **代码质量**：命名规范、代码复杂度、重复代码、错误处理
4. **可维护性**：是否有适当的类型注解、文档字符串、模块化设计
5. **性能**：是否存在明显的性能问题

输出 JSON 格式：
{
  "score": 85,
  "passed": true/false,
  "issues": ["问题1", "问题2"],
  "suggestions": ["改进建议1", "改进建议2"],
  "security_concerns": [],
  "summary": "总体评价"
}

评分标准：
- 90-100: 优秀，可以直接合并
- 75-89: 良好，有小问题需要修复
- 60-74: 及格，有重要问题需要修复
- <60: 不及格，需要重写
"""


def create_reviewer_prompt(state: AgentState) -> str:
    product_spec = state.get("product_spec", "")
    files = state.get("generated_files", [])

    # Format generated files for review
    files_text = ""
    for f in files:
        files_text += f"\n### {f.get('path', 'unknown')}\n```\n{f.get('content', '')[:2000]}\n```\n"

    return f"""请审查以下代码：

## 原始需求规格
{product_spec[:2000] if product_spec else "无"}

## 生成的代码文件
{files_text if files_text else "无代码文件"}

请给出评分和详细的审查意见。"""


def parse_review_response(response: str) -> ReviewResult:
    import json
    content = response.strip()

    if "```json" in content:
        start = content.find("```json") + 7
        end = content.find("```", start)
        content = content[start:end].strip()
    elif "```" in content:
        start = content.find("```") + 3
        end = content.find("```", start)
        content = content[start:end].strip()

    try:
        result = json.loads(content)
        return ReviewResult(
            score=result.get("score", 0),
            issues=result.get("issues", []),
            suggestions=result.get("suggestions", []),
            passed=result.get("passed", result.get("score", 0) >= 75),
        )
    except json.JSONDecodeError:
        return ReviewResult(
            score=0,
            issues=["Failed to parse review response"],
            suggestions=["Retry code generation"],
            passed=False,
        )


def run_reviewer(state: AgentState) -> dict:
    """Execute the Reviewer agent."""
    client = create_llm_client()
    model = get_model_name()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": create_reviewer_prompt(state)},
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        max_tokens=2048,
    )

    result_text = response.choices[0].message.content
    review = parse_review_response(result_text)

    return {
        "review_result": review,
        "review_iteration": state.get("review_iteration", 0) + 1,
        "messages": [{
            "role": "assistant",
            "content": f"Review score: {review['score']}/100. Passed: {review['passed']}",
            "agent": "reviewer",
        }],
    }

"""Reviewer Agent — reviews generated code for quality, security, and correctness."""

import json
import re
from src.config.llm_config import create_llm_client, get_model_name
from src.state.workflow_state import AgentState, ReviewResult


SYSTEM_PROMPT = """你是一位严格的代码审查员（Code Reviewer）。审查代码质量并输出 JSON 结果。

审查维度：正确性、安全性、代码质量、可维护性、性能。

严格输出 JSON（不要 markdown 包装）：
{"score": 85, "passed": true, "issues": ["问题1"], "suggestions": ["建议1"], "summary": "总体评价"}

passed 为 true 的条件是 score >= 75。"""


def create_reviewer_prompt(state: AgentState) -> str:
    product_spec = state.get("product_spec", "")
    files = state.get("generated_files", [])

    files_text = ""
    for f in files:
        files_text += f"\n### {f.get('path', 'unknown')}\n```\n{f.get('content', '')[:2000]}\n```\n"

    return f"""审查以下代码：

## 需求规格
{product_spec[:2000] if product_spec else "无"}

## 代码文件
{files_text if files_text else "无代码文件"}

输出 JSON。"""


def parse_review_response(response: str) -> ReviewResult:
    """Robust multi-strategy review response parser."""
    content = response.strip()

    # Strategy 1: Extract from ```json block
    json_str = None
    if "```json" in content:
        start = content.find("```json") + 7
        end = content.find("```", start)
        json_str = content[start:end].strip()
    elif "```" in content:
        start = content.find("```") + 3
        end = content.find("```", start)
        candidate = content[start:end].strip()
        if candidate.startswith("{"):
            json_str = candidate

    # Strategy 2: Find JSON object in response
    if json_str is None:
        brace_start = content.find("{")
        brace_end = content.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            json_str = content[brace_start:brace_end + 1]

    # Attempt JSON parse
    if json_str:
        try:
            result = json.loads(json_str)
            return _build_result(result)
        except json.JSONDecodeError:
            pass

    # Strategy 3: Try whole response as JSON
    try:
        result = json.loads(content)
        return _build_result(result)
    except json.JSONDecodeError:
        pass

    # Strategy 4: Extract score and issues from markdown text
    score_match = re.search(r'(?:score|评分|分数)[:\s]*(\d+)', content, re.IGNORECASE)
    score = int(score_match.group(1)) if score_match else 50

    # Extract bullet points as issues/suggestions
    issues = []
    suggestions = []
    in_issues = False
    in_suggestions = False
    for line in content.split("\n"):
        line = line.strip()
        if re.search(r'(?:问题|issues|缺陷)', line, re.IGNORECASE):
            in_issues = True
            in_suggestions = False
            continue
        if re.search(r'(?:建议|suggestions|改进)', line, re.IGNORECASE):
            in_suggestions = True
            in_issues = False
            continue
        if line.startswith(("- ", "* ", "• ", "· ")):
            item = line[2:].strip()
            if in_suggestions:
                suggestions.append(item)
            elif in_issues:
                issues.append(item)

    return ReviewResult(
        score=score,
        issues=issues if issues else ["Review output not in expected JSON format"],
        suggestions=suggestions if suggestions else ["Ensure JSON output format for next review"],
        passed=score >= 75,
    )


def _build_result(data: dict) -> ReviewResult:
    return ReviewResult(
        score=int(data.get("score", 0)),
        issues=data.get("issues", []),
        suggestions=data.get("suggestions", []),
        passed=data.get("passed", int(data.get("score", 0)) >= 75),
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
        max_tokens=4096,
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

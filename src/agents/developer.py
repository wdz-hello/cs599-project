"""Developer Agent — generates code based on SDD specs."""

from src.config.llm_config import create_llm_client, get_model_name
from src.state.workflow_state import AgentState


SYSTEM_PROMPT = """你是一位资深软件工程师。你的任务是根据规格文档生成高质量代码。

规则：
1. 按照 Product Spec 的功能需求和 API Spec 的接口契约编写代码
2. 代码必须可运行，包含完整的导入语句和类型注解
3. 遵循 PEP 8 规范和行业最佳实践
4. 包含适当的错误处理
5. 输出 JSON 格式，每个文件包含 path、content 和 action（create/update）

输出格式：
{
  "files": [
    {"path": "relative/path/to/file.py", "content": "...", "action": "create"},
    ...
  ],
  "summary": "简要说明生成了哪些文件及其用途"
}
"""


def create_developer_prompt(state: AgentState) -> str:
    product_spec = state.get("product_spec", "")
    architecture_spec = state.get("architecture_spec", "")
    api_spec = state.get("api_spec", "")
    language = state.get("target_language", "python")
    iteration = state.get("coding_iteration", 0)

    # Include review feedback if this is a revision
    review_feedback = ""
    review = state.get("review_result")
    if review and not review.get("passed", False) and iteration > 0:
        issues = review.get("issues", [])
        suggestions = review.get("suggestions", [])
        review_feedback = f"""
## 代码审查反馈（需要修复）
**问题：**
{chr(10).join(f'- {i}' for i in issues)}
**建议：**
{chr(10).join(f'- {s}' for s in suggestions)}
"""

    # Include test feedback
    test_feedback = ""
    test_result = state.get("test_result")
    if test_result and test_result.get("failed", 0) > 0:
        details = test_result.get("details", [])
        test_feedback = f"""
## 测试失败信息
{chr(10).join(f'- {d}' for d in details)}
"""

    return f"""请根据以下规格文档生成代码：

## 产品规格
{product_spec[:3000] if product_spec else "无产品规格"}

## 架构规格
{architecture_spec[:3000] if architecture_spec else "无架构规格"}

## API 规格
{api_spec[:2000] if api_spec else "无 API 规格"}

## 目标语言
{language}
{review_feedback}
{test_feedback}

请生成完整的代码文件列表。确保代码可以直接运行。"""


def parse_developer_response(response: str, base_dir: str = "src/generated") -> list[dict]:
    """Parse code generation response."""
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
        return result.get("files", [])
    except json.JSONDecodeError:
        # Fallback: try to extract code blocks
        files = []
        import re
        blocks = re.findall(r'```(\w+)?\n(.*?)```', response, re.DOTALL)
        for i, (lang, code) in enumerate(blocks):
            ext = ".py" if not lang or lang == "python" else f".{lang}"
            files.append({
                "path": f"{base_dir}/file_{i}{ext}",
                "content": code.strip(),
                "action": "create",
            })
        return files


def run_developer(state: AgentState) -> dict:
    """Execute the Developer agent."""
    client = create_llm_client()
    model = get_model_name()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": create_developer_prompt(state)},
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        max_tokens=4096,
    )

    result_text = response.choices[0].message.content
    files = parse_developer_response(result_text)

    return {
        "generated_files": files,
        "coding_iteration": state.get("coding_iteration", 0) + 1,
        "messages": [{
            "role": "assistant",
            "content": f"Generated {len(files)} file(s).",
            "agent": "developer",
        }],
    }

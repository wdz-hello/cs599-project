"""Developer Agent — generates code based on SDD specs."""

from src.config.llm_config import create_llm_client, get_model_name
from src.state.workflow_state import AgentState


SYSTEM_PROMPT = """你是一位资深软件工程师。你的任务是根据规格文档生成高质量代码。

规则：
1. 按照 Product Spec 的功能需求和 API Spec 的接口契约编写代码
2. 代码必须可运行，包含完整的导入语句和类型注解
3. 遵循 PEP 8 规范和行业最佳实践
4. 每个文件使用唯一的文件名（如 main.py, models.py, utils.py），不要重复
5. 函数实现必须完整，不能截断或留空
6. 输出 JSON 格式，每个文件包含 path、content 和 action（create/update）

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
    is_revision = False
    review_feedback = ""
    review = state.get("review_result")
    if review and not review.get("passed", False) and iteration > 0:
        is_revision = True
        issues = review.get("issues", [])
        suggestions = review.get("suggestions", [])
        review_feedback = f"""
## 代码审查反馈（需要修复 — 第 {iteration} 次迭代）
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

    # Show existing files in revision mode
    existing_files_info = ""
    if is_revision:
        existing = state.get("generated_files", [])
        if existing:
            existing_files_info = "\n## 已生成的文件（请只修改有问题的文件，不要重复生成）\n"
            for ef in existing:
                existing_files_info += f"- {ef.get('path', '?')}\n"
            existing_files_info += "\n对于已有文件使用 action: \"update\"，仅对全新文件使用 action: \"create\"。"

    return f"""请根据以下规格文档生成代码：

## 产品规格
{product_spec[:3000] if product_spec else "无产品规格"}

## 架构规格
{architecture_spec[:3000] if architecture_spec else "无架构规格"}

## API 规格
{api_spec[:2000] if api_spec else "无 API 规格"}

## 目标语言
{language}
{existing_files_info}
{review_feedback}
{test_feedback}

{'请只修复审查反馈中提到的具体问题，不要重新生成所有文件。' if is_revision else '请生成完整的代码文件列表。确保代码可以直接运行。'}"""


def parse_developer_response(response: str, base_dir: str = "src/generated") -> list[dict]:
    """Parse code generation response — robust multi-strategy parser."""
    import json, re
    content = response.strip()

    # Strategy 1: Extract JSON from ```json blocks
    json_str = None
    if "```json" in content:
        start = content.find("```json") + 7
        end = content.find("```", start)
        json_str = content[start:end].strip()
    elif "```" in content:
        # Check if the first code block looks like JSON
        start = content.find("```") + 3
        end = content.find("```", start)
        candidate = content[start:end].strip()
        if candidate.startswith("{") and "files" in candidate:
            json_str = candidate

    # Try parsing as pure JSON if no code block found
    if json_str is None:
        # Strip markdown preamble (text before first {)
        brace_idx = content.find("{")
        if brace_idx >= 0:
            json_str = content[brace_idx:]

    # Attempt JSON parse
    if json_str:
        try:
            result = json.loads(json_str)
            files = result.get("files", [])
            return _normalize_files(files, base_dir)
        except json.JSONDecodeError:
            pass

    # Strategy 2: Try parsing entire response as JSON
    try:
        result = json.loads(content)
        files = result.get("files", [])
        return _normalize_files(files, base_dir)
    except json.JSONDecodeError:
        pass

    # Strategy 3: Extract Python code blocks from markdown
    py_blocks = re.findall(r'```(?:python|py)?\s*\n(.*?)```', response, re.DOTALL | re.IGNORECASE)
    if py_blocks:
        files = []
        for i, code in enumerate(py_blocks):
            code = code.strip()
            if not code:
                continue
            # Try to guess filename from content
            filename = _guess_filename(code, i)
            files.append({
                "path": f"{base_dir}/{filename}",
                "content": code,
                "action": "create",
            })
        if files:
            return files

    # Strategy 4: Generic code block extraction
    blocks = re.findall(r'```(?:\w*)\s*\n(.*?)```', response, re.DOTALL)
    if blocks:
        files = []
        for i, code in enumerate(blocks):
            code = code.strip()
            if not code:
                continue
            filename = _guess_filename(code, i)
            files.append({
                "path": f"{base_dir}/{filename}",
                "content": code,
                "action": "create",
            })
        if files:
            return files

    # Strategy 5: Treat entire response as a single Python file
    if content and ("def " in content or "class " in content or "import " in content):
        return [{
            "path": f"{base_dir}/main.py",
            "content": content,
            "action": "create",
        }]

    return []


def _normalize_files(files: list[dict], base_dir: str) -> list[dict]:
    """Ensure every file entry has required fields and unique paths.

    For 'update' actions on existing paths, replaces the old entry.
    For 'create' actions on duplicate paths, adds a numeric suffix.
    """
    for f in files:
        f.setdefault("action", "create")
        if "path" not in f:
            f["path"] = f"{base_dir}/generated_file.py"

    # Deduplicate: update actions replace same-path files, creates get unique names
    seen = {}  # path -> index
    result = []
    for f in files:
        p = f["path"]
        if p in seen:
            if f.get("action") == "update":
                # Replace the previous version with updated content
                result[seen[p]] = f
                continue
            # Create action with duplicate name: add suffix
            base, ext = p.rsplit(".", 1) if "." in p else (p, "py")
            counter = 1
            while p in seen:
                p = f"{base}_{counter}.{ext}"
                counter += 1
            f["path"] = p
        seen[p] = len(result)
        result.append(f)
    return result


def _guess_filename(code: str, index: int) -> str:
    """Guess a sensible filename from code content."""
    import re
    # Look for test files first
    if 'unittest' in code or 'pytest' in code or re.search(r'def test_\w+', code):
        return f"test_module_{index}.py"
    # Look for Flask/FastAPI apps
    if re.search(r'from flask|from fastapi|Flask\(|FastAPI\(', code):
        return "app.py"
    # Look for class definitions
    class_match = re.search(r'class\s+(\w+)', code)
    if class_match:
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', class_match.group(1)).lower()
        return f"{name}.py"
    # Look for main guard
    if 'if __name__' in code:
        return "main.py"
    return f"module_{index}.py"


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
        max_tokens=8192,
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

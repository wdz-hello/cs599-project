"""QA Agent — generates test cases and evaluates test results."""

from src.config.llm_config import create_llm_client, get_model_name
from src.state.workflow_state import AgentState, TestResult


SYSTEM_PROMPT = """你是一位 QA 测试工程师。你的任务是为代码生成测试用例。

测试策略：
1. 为每个函数/方法生成单元测试
2. 覆盖正常路径和边界条件
3. 包含异常处理测试
4. 使用 pytest 框架

输出 JSON 格式：
{
  "test_file": "完整的可运行测试代码",
  "test_plan": "测试策略说明",
  "estimated_coverage": 85,
  "test_cases": ["用例1", "用例2", ...]
}
"""


def create_qa_prompt(state: AgentState) -> str:
    files = state.get("generated_files", [])
    product_spec = state.get("product_spec", "")

    files_text = ""
    for f in files:
        files_text += f"\n### {f.get('path', 'unknown')}\n```\n{f.get('content', '')[:2000]}\n```\n"

    return f"""请为以下代码生成完整的测试套件：

## 需求说明
{product_spec[:1500] if product_spec else "无"}

## 源代码
{files_text if files_text else "无代码文件"}

请使用 pytest 框架，确保测试可以直接运行（python -m pytest）。"""


def parse_qa_response(response: str) -> dict:
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
        return result
    except json.JSONDecodeError:
        # Fallback: extract python test code
        import re
        test_match = re.search(r'```python\n(.*?)```', response, re.DOTALL)
        test_code = test_match.group(1) if test_match else ""
        return {
            "test_file": test_code,
            "test_plan": "Auto-generated tests",
            "estimated_coverage": 0,
            "test_cases": [],
        }


def run_qa_agent(state: AgentState) -> dict:
    """Execute the QA agent to generate tests."""
    client = create_llm_client()
    model = get_model_name()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": create_qa_prompt(state)},
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        max_tokens=4096,
    )

    result_text = response.choices[0].message.content
    qa_result = parse_qa_response(result_text)

    test_file = qa_result.get("test_file", "")

    # Try to run the tests
    test_execution = _run_tests(test_file)

    return {
        "test_result": test_execution,
        "test_iteration": state.get("test_iteration", 0) + 1,
        "generated_files": [{
            "path": "tests/test_generated.py",
            "content": test_file,
            "action": "create",
        }],
        "messages": [{
            "role": "assistant",
            "content": f"Tests generated. {test_execution.get('passed', 0)}/{test_execution.get('total', 0)} passed.",
            "agent": "qa",
        }],
    }


def _run_tests(test_code: str) -> TestResult:
    """Execute generated tests in a subprocess and parse results."""
    import subprocess
    import tempfile
    import os

    if not test_code.strip():
        return TestResult(total=0, passed=0, failed=0, details=["No test code to run"], coverage=0.0)

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(test_code)
            temp_path = f.name

        result = subprocess.run(
            ["python", "-m", "pytest", temp_path, "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        os.unlink(temp_path)

        output = result.stdout + result.stderr
        lines = output.split("\n")

        # Parse pytest summary
        passed = 0
        failed = 0
        for line in lines:
            if "passed" in line and "failed" in line:
                import re
                p = re.search(r'(\d+) passed', line)
                f_match = re.search(r'(\d+) failed', line)
                passed = int(p.group(1)) if p else 0
                failed = int(f_match.group(1)) if f_match else 0
                break

        return TestResult(
            total=passed + failed,
            passed=passed,
            failed=failed,
            details=lines[-20:],  # last 20 lines
            coverage=0.0,
        )

    except subprocess.TimeoutExpired:
        return TestResult(
            total=0, passed=0, failed=1,
            details=["Test execution timed out (30s)"],
            coverage=0.0,
        )
    except Exception as e:
        return TestResult(
            total=0, passed=0, failed=1,
            details=[f"Test execution error: {str(e)}"],
            coverage=0.0,
        )

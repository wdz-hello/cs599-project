"""Spec Architect Agent — analyzes requirements and generates SDD spec documents."""

from langchain_core.tools import tool
from src.config.llm_config import create_llm_client, get_model_name
from src.state.workflow_state import AgentState
import json


SYSTEM_PROMPT = """你是一位资深软件架构师，专精于规格驱动开发（SDD）。

你的职责：
1. 分析用户需求，理解其核心意图
2. 生成产品规格文档（Product Spec）：定义功能需求、用户故事、验收标准
3. 生成架构规格文档（Architecture Spec）：定义系统组件、技术栈、数据流
4. 生成 API 规格文档（API Spec）：定义接口契约、数据模型

输出格式要求：使用 Markdown，结构清晰，包含具体的技术细节而非泛泛而谈。
输出必须是合法的 JSON，格式为：
{
  "product_spec": "...",
  "architecture_spec": "...",
  "api_spec": "...",
  "analysis": "..."
}
"""


def create_spec_architect_prompt(state: AgentState) -> str:
    requirement = state.get("requirement", "")
    context = state.get("project_context", "")
    language = state.get("target_language", "python")
    revision_count = state.get("spec_revision_count", 0)

    revision_note = ""
    if revision_count > 0:
        revision_note = f"\n这是第 {revision_count} 次修订。请根据反馈改进规格文档。"

    return f"""请为以下软件需求生成完整的 SDD 规格文档：

## 用户需求
{requirement}

## 项目上下文
{context if context else "无额外上下文"}

## 目标语言
{language}
{revision_note}

请输出包含 product_spec、architecture_spec、api_spec 三个部分的 JSON。"""


def parse_spec_response(response: str) -> dict:
    """Parse the LLM response to extract spec documents."""
    content = response.strip()

    # Try to extract JSON from markdown code blocks
    if "```json" in content:
        start = content.find("```json") + 7
        end = content.find("```", start)
        content = content[start:end].strip()
    elif "```" in content:
        start = content.find("```") + 3
        end = content.find("```", start)
        content = content[start:end].strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "product_spec": content,
            "architecture_spec": "",
            "api_spec": "",
            "analysis": "Failed to parse structured JSON output",
        }


def run_spec_architect(state: AgentState) -> dict:
    """Execute the Spec Architect agent.

    Takes current AgentState, returns updates to merge into state.
    """
    client = create_llm_client()
    model = get_model_name()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": create_spec_architect_prompt(state)},
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        max_tokens=4096,
    )

    result_text = response.choices[0].message.content
    specs = parse_spec_response(result_text)

    return {
        "product_spec": specs.get("product_spec", ""),
        "architecture_spec": specs.get("architecture_spec", ""),
        "api_spec": specs.get("api_spec", ""),
        "spec_revision_count": state.get("spec_revision_count", 0) + 1,
        "messages": [{
            "role": "assistant",
            "content": specs.get("analysis", "Spec documents generated."),
            "agent": "spec_architect",
        }],
    }

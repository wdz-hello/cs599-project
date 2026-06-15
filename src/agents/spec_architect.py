"""Spec Architect Agent — analyzes requirements and generates SDD spec documents."""

import re
from src.config.llm_config import create_llm_client, get_model_name
from src.state.workflow_state import AgentState


SYSTEM_PROMPT = """你是一位资深软件架构师，专精于规格驱动开发（SDD）。

你的职责：分析用户需求，生成三份结构化的规格文档。

严格按以下 Markdown 格式输出，每份文档以二级标题开头：

## Product Spec
（产品规格：功能概述、用户故事、功能需求列表、非功能需求、验收标准）

## Architecture Spec
（架构规格：系统架构图 ASCII art、组件说明、技术栈选择及理由、数据流设计、部署方案）

## API Spec
（API 规格：接口定义、数据模型、请求/响应格式、错误码定义）

## Analysis
（简要分析：技术方案总结、关键设计决策、风险点）

注意：
- 每份文档内容要具体，包含代码示例和具体的技术参数
- 不要输出 JSON 格式，直接输出 Markdown
- 使用二级标题 ## 分隔每个部分
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

请按格式输出 Product Spec、Architecture Spec、API Spec 和 Analysis 四个部分。"""


def parse_spec_response(response: str) -> dict:
    """Parse markdown-structured spec response by splitting on ## headings."""
    content = response.strip()

    # Extract sections by ## headings
    sections = {"product_spec": "", "architecture_spec": "", "api_spec": "", "analysis": ""}

    # Split on ## heading markers
    pattern = r'##\s+(Product Spec|Architecture Spec|API Spec|Analysis)'
    parts = re.split(pattern, content, flags=re.IGNORECASE)

    # parts[0] is before first heading, then alternating (heading, content)
    for i in range(1, len(parts), 2):
        heading = parts[i].strip().lower()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""

        if "product" in heading:
            sections["product_spec"] = body
        elif "architect" in heading:
            sections["architecture_spec"] = body
        elif "api" in heading:
            sections["api_spec"] = body
        elif "analysis" in heading:
            sections["analysis"] = body

    # Fallback: if no sections were parsed, treat whole response as product_spec
    if not any(sections.values()):
        sections["product_spec"] = content
        sections["analysis"] = "Failed to parse structured output — using raw response as product spec."

    return sections


def run_spec_architect(state: AgentState) -> dict:
    """Execute the Spec Architect agent."""
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
        max_tokens=8192,
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

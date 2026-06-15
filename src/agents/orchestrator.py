"""Orchestrator — LangGraph StateGraph coordinating the multi-agent workflow.

Workflow:
    START -> spec_architect -> [gate: spec valid?]
        -> developer -> [gate: files generated?]
        -> reviewer -> [gate: review passed?]
        -> qa_agent -> [gate: tests passed?]
        -> finalize -> END
"""

from langgraph.graph import StateGraph, END
from src.state.workflow_state import AgentState, WorkflowPhase
from src.agents.spec_architect import run_spec_architect
from src.agents.developer import run_developer
from src.agents.reviewer import run_reviewer
from src.agents.qa import run_qa_agent


# ── Node functions ──────────────────────────────────────────────

def node_spec_architect(state: AgentState) -> dict:
    """Node: run Spec Architect agent."""
    result = run_spec_architect(state)
    result["phase"] = WorkflowPhase.SPEC_REVIEW
    return result


def node_developer(state: AgentState) -> dict:
    """Node: run Developer agent."""
    result = run_developer(state)
    result["phase"] = WorkflowPhase.CODE_REVIEW
    return result


def node_reviewer(state: AgentState) -> dict:
    """Node: run Reviewer agent."""
    result = run_reviewer(state)
    return result


def node_qa_agent(state: AgentState) -> dict:
    """Node: run QA agent."""
    result = run_qa_agent(state)
    return result


def node_finalize(state: AgentState) -> dict:
    """Node: produce final report."""
    review = state.get("review_result", {})
    test_result = state.get("test_result", {})
    files = state.get("generated_files", [])

    report_parts = [
        "# DevMind — 项目生成报告",
        "",
        f"## 代码审查结果",
        f"- 评分: {review.get('score', 'N/A')}/100",
        f"- 通过: {review.get('passed', False)}",
    ]

    if review.get("issues"):
        report_parts.append("\n### 发现的问题")
        for issue in review["issues"]:
            report_parts.append(f"- {issue}")

    report_parts.extend([
        "",
        "## 测试结果",
        f"- 总计: {test_result.get('total', 0)}",
        f"- 通过: {test_result.get('passed', 0)}",
        f"- 失败: {test_result.get('failed', 0)}",
        "",
        "## 生成的文件",
    ])

    for f in files:
        report_parts.append(f"- `{f.get('path', 'unknown')}`")

    return {
        "phase": WorkflowPhase.COMPLETE,
        "final_report": "\n".join(report_parts),
        "messages": [{
            "role": "system",
            "content": "Workflow completed successfully.",
            "agent": "orchestrator",
        }],
    }


def node_handle_error(state: AgentState) -> dict:
    """Node: handle errors gracefully."""
    return {
        "phase": WorkflowPhase.ERROR,
        "messages": [{
            "role": "system",
            "content": f"Workflow stopped due to: {state.get('error_message', 'Unknown error')}",
            "agent": "orchestrator",
        }],
    }


# ── Routing functions ───────────────────────────────────────────

def gate_after_spec(state: AgentState) -> str:
    """Route after spec architect: check if specs are valid."""
    product_spec = state.get("product_spec", "")
    revision_count = state.get("spec_revision_count", 0)
    max_iter = state.get("max_iterations", 3)

    if not product_spec:
        if revision_count >= max_iter:
            return "handle_error"
        return "spec_architect"

    return "developer"


def gate_after_developer(state: AgentState) -> str:
    """Route after developer: check if files were generated."""
    files = state.get("generated_files", [])
    if not files:
        iteration = state.get("coding_iteration", 0)
        if iteration >= state.get("max_iterations", 3):
            return "handle_error"
        return "developer"

    return "reviewer"


def gate_after_reviewer(state: AgentState) -> str:
    """Route after reviewer: check if review passed."""
    review = state.get("review_result")
    if not review:
        return "handle_error"

    if review.get("passed", False):
        return "qa_agent"

    iteration = state.get("review_iteration", 0)
    max_iter = state.get("max_iterations", 3)
    if iteration >= max_iter:
        return "qa_agent"  # proceed anyway after max retries

    return "developer"  # send back for fixes


def gate_after_qa(state: AgentState) -> str:
    """Route after QA: check test results."""
    test_result = state.get("test_result")
    if not test_result:
        return "finalize"

    if test_result.get("failed", 0) == 0:
        return "finalize"

    iteration = state.get("test_iteration", 0)
    max_iter = state.get("max_iterations", 3)
    if iteration >= max_iter:
        return "finalize"  # proceed anyway

    return "developer"  # send back for fixes


# ── Build the graph ──────────────────────────────────────────────

def create_workflow() -> StateGraph:
    """Create and return the compiled LangGraph workflow."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("spec_architect", node_spec_architect)
    workflow.add_node("developer", node_developer)
    workflow.add_node("reviewer", node_reviewer)
    workflow.add_node("qa_agent", node_qa_agent)
    workflow.add_node("finalize", node_finalize)
    workflow.add_node("handle_error", node_handle_error)

    # Set entry point
    workflow.set_entry_point("spec_architect")

    # Add conditional edges
    workflow.add_conditional_edges(
        "spec_architect",
        gate_after_spec,
        {
            "spec_architect": "spec_architect",
            "developer": "developer",
            "handle_error": "handle_error",
        },
    )

    workflow.add_conditional_edges(
        "developer",
        gate_after_developer,
        {
            "developer": "developer",
            "reviewer": "reviewer",
            "handle_error": "handle_error",
        },
    )

    workflow.add_conditional_edges(
        "reviewer",
        gate_after_reviewer,
        {
            "developer": "developer",
            "qa_agent": "qa_agent",
            "handle_error": "handle_error",
        },
    )

    workflow.add_conditional_edges(
        "qa_agent",
        gate_after_qa,
        {
            "developer": "developer",
            "finalize": "finalize",
            "handle_error": "handle_error",
        },
    )

    # Terminal nodes
    workflow.add_edge("finalize", END)
    workflow.add_edge("handle_error", END)

    return workflow.compile()


# ── Convenience runner ───────────────────────────────────────────

def run_workflow(requirement: str, project_context: str = "", target_language: str = "python") -> AgentState:
    """Run the full DevMind workflow end-to-end.

    Args:
        requirement: Natural language description of the software to build.
        project_context: Optional additional context.
        target_language: Target programming language (default: python).

    Returns:
        Final AgentState with all outputs.
    """
    workflow = create_workflow()

    initial_state: AgentState = {
        "phase": WorkflowPhase.INIT,
        "messages": [],
        "requirement": requirement,
        "project_context": project_context,
        "target_language": target_language,
        "product_spec": None,
        "architecture_spec": None,
        "api_spec": None,
        "spec_revision_count": 0,
        "generated_files": [],
        "coding_iteration": 0,
        "review_result": None,
        "review_iteration": 0,
        "test_result": None,
        "test_iteration": 0,
        "max_iterations": 3,
        "error_message": None,
        "final_report": None,
    }

    return workflow.invoke(initial_state)

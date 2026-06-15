"""DevMind Streamlit Web UI — interactive multi-agent development assistant."""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from src.agents.orchestrator import create_workflow
from src.state.workflow_state import AgentState, WorkflowPhase
from src.config.settings import settings
from src.memory.short_term import ConversationMemory
from src.evaluation.tracing import trace_manager


st.set_page_config(
    page_title="DevMind — 多智能体软件开发助手",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ─────────────────────────────────────────────────────

with st.sidebar:
    st.title("🧠 DevMind")
    st.caption("SDD 驱动的多智能体软件开发助手")

    st.divider()

    st.subheader("⚙️ 配置")
    try:
        settings.validate()
        st.success(f"LLM: {settings.DEEPSEEK_MODEL}")
    except ValueError:
        st.error("❌ 请配置 .env 文件中的 DEEPSEEK_API_KEY")
        st.code("DEEPSEEK_API_KEY=sk-your-key-here", language="bash")

    st.divider()

    st.subheader("📋 工作流阶段")
    phases_order = [
        ("INIT", "初始化"),
        ("SPEC_WRITING", "规格编写"),
        ("SPEC_REVIEW", "规格审查"),
        ("CODING", "代码生成"),
        ("CODE_REVIEW", "代码审查"),
        ("TESTING", "测试验证"),
        ("COMPLETE", "完成"),
    ]
    for phase_id, phase_label in phases_order:
        st.text(f"  {'◻' if 'current' not in st.session_state else '●'} {phase_label}")

    st.divider()

    st.subheader("📊 会话统计")
    if "total_runs" in st.session_state:
        st.metric("已运行", st.session_state.total_runs)

    if st.button("🔄 重置会话"):
        st.session_state.clear()
        st.rerun()

# ── Main Content ─────────────────────────────────────────────────

st.title("DevMind — SDD 驱动的多智能体软件开发助手")
st.caption("输入自然语言需求 → 多 Agent 协作 → 生成可运行的代码 + 审查报告 + 测试用例")

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "workflow_completed" not in st.session_state:
    st.session_state.workflow_completed = False
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "total_runs" not in st.session_state:
    st.session_state.total_runs = 0

# ── Input Area ───────────────────────────────────────────────────

st.subheader("📝 需求输入")

col1, col2 = st.columns([3, 1])

with col1:
    requirement = st.text_area(
        "描述你想要开发的软件需求",
        placeholder="例如：\n设计一个简单的 REST API 服务，支持用户注册和登录功能。\n要求：\n1. 使用 Flask 框架\n2. 支持 JWT 认证\n3. 包含单元测试",
        height=150,
    )

with col2:
    target_language = st.selectbox("目标语言", ["python", "javascript", "typescript"], index=0)
    project_context = st.text_area("项目上下文（可选）", placeholder="已有的技术栈、约束条件等", height=80)
    max_iterations = st.slider("最大迭代次数", 1, 5, 3)

    run_button = st.button("🚀 启动工作流", type="primary", use_container_width=True)

# ── Run Workflow ─────────────────────────────────────────────────

if run_button and requirement.strip():
    st.divider()

    progress_container = st.container()
    result_container = st.container()

    with progress_container:
        st.subheader("🔄 工作流执行中...")
        progress_bar = st.progress(0, text="初始化...")
        status_area = st.empty()

    # Setup initial state
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
        "max_iterations": max_iterations,
        "error_message": None,
        "final_report": None,
    }

    # Create and run workflow
    workflow = create_workflow()

    # Use streaming to show progress
    phases_progress = {
        WorkflowPhase.SPEC_WRITING: (10, "Spec Architect 分析需求中..."),
        WorkflowPhase.SPEC_REVIEW: (25, "规格文档已生成"),
        WorkflowPhase.CODING: (50, "Developer Agent 生成代码中..."),
        WorkflowPhase.CODE_REVIEW: (75, "Reviewer Agent 审查代码中..."),
        WorkflowPhase.TESTING: (90, "QA Agent 生成测试中..."),
        WorkflowPhase.COMPLETE: (100, "工作流完成！"),
    }

    # Start trace
    trace_id = trace_manager.start_trace("web_ui_run", {"requirement": requirement[:100]})

    try:
        # Execute workflow
        with st.spinner("Agent 工作中..."):
            result = workflow.invoke(initial_state)

        # Update progress
        phase = result.get("phase", WorkflowPhase.ERROR)
        for p, (progress_val, status_text) in phases_progress.items():
            if phase == p or list(WorkflowPhase).index(phase) >= list(WorkflowPhase).index(p):
                progress_bar.progress(progress_val, text=status_text)

        st.session_state.last_result = result
        st.session_state.workflow_completed = True
        st.session_state.total_runs += 1
        st.session_state.chat_history.append({
            "requirement": requirement,
            "result_summary": "Completed" if phase == WorkflowPhase.COMPLETE else f"Ended at {phase}",
        })

        trace_manager.end_trace(trace_id, "success")

    except Exception as e:
        progress_bar.progress(0, text=f"错误: {str(e)}")
        status_area.error(f"❌ 工作流执行失败: {str(e)}")
        trace_manager.end_trace(trace_id, "error")
        st.stop()

    # ── Results Display ──────────────────────────────────────────

    with result_container:
        st.divider()
        st.subheader("📊 执行结果")

        # Tabs for different result views
        tab1, tab2, tab3, tab4 = st.tabs([
            "📋 规格文档",
            "💻 生成代码",
            "🔍 审查报告",
            "🧪 测试结果",
        ])

        with tab1:
            st.markdown("### Product Spec")
            product_spec = result.get("product_spec")
            if product_spec:
                st.markdown(product_spec)
            else:
                st.info("暂无产品规格")

            with st.expander("Architecture Spec"):
                arch_spec = result.get("architecture_spec")
                st.markdown(arch_spec if arch_spec else "暂无架构规格")

            with st.expander("API Spec"):
                api_spec = result.get("api_spec")
                st.markdown(api_spec if api_spec else "暂无 API 规格")

        with tab2:
            files = result.get("generated_files", [])
            if files:
                st.metric("生成文件数", len(files))
                for i, f in enumerate(files):
                    with st.expander(f"📄 {f.get('path', f'file_{i}')} ({f.get('action', 'create')})"):
                        st.code(f.get("content", "(empty)"), language=target_language)
            else:
                st.info("暂无生成的文件")

        with tab3:
            review = result.get("review_result")
            if review:
                col_score, col_passed = st.columns(2)
                with col_score:
                    score = review.get("score", 0)
                    color = "green" if score >= 75 else "orange" if score >= 60 else "red"
                    st.metric("评分", f"{score}/100", delta=None)
                with col_passed:
                    st.metric("状态", "✅ 通过" if review.get("passed") else "❌ 未通过")

                st.subheader("问题")
                for issue in review.get("issues", []):
                    st.warning(issue)

                st.subheader("建议")
                for suggestion in review.get("suggestions", []):
                    st.info(suggestion)
            else:
                st.info("暂无审查结果")

        with tab4:
            test_result = result.get("test_result")
            if test_result:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("总计", test_result.get("total", 0))
                with col2:
                    st.metric("通过", test_result.get("passed", 0), delta=None)
                with col3:
                    st.metric("失败", test_result.get("failed", 0))

                st.subheader("详情")
                for detail in test_result.get("details", []):
                    st.text(detail)
            else:
                st.info("暂无测试结果")

        # Final report
        st.divider()
        st.subheader("📝 最终报告")
        final_report = result.get("final_report")
        if final_report:
            st.markdown(final_report)
        else:
            st.info("报告生成中...")

    st.balloons()


elif run_button and not requirement.strip():
    st.error("请输入需求描述")

# ── Footer ───────────────────────────────────────────────────────

st.divider()
st.caption("DevMind · CS599 期末大作业 · 方向一：Agentic AI 原生开发")

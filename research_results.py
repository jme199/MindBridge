import streamlit as st

def result_ui_text(en, zh):
    """Return report UI text in the selected language."""
    return (
        zh
        if st.session_state.get("ui_language", "EN") == "中文"
        else en
    )


# =========================================================
# Demo Data
# =========================================================

DEMO_RESEARCH_RESULT = {
    "status": "demo",
    "topic": "Exam Anxiety",
    "summary": (
        "Research suggests that some psychological and "
        "behavioural approaches may help reduce test anxiety "
        "among university students. However, effectiveness "
        "varies across individuals and studies."
    ),
    "papers": [
        {
            "title": "Demonstration Study A — Exam Anxiety",
            "authors": "Example Authors",
            "year": "Demo",
            "study_type": "Illustrative meta-analysis",
            "doi": None,
            "finding": (
                "Illustrative finding: structured psychological "
                "support may help some students manage exam anxiety."
            ),
            "limitations": (
                "Demonstration content only. This is not a "
                "verified scientific publication."
            ),
        },
        {
            "title": "Demonstration Study B — Student Well-being",
            "authors": "Example Authors",
            "year": "Demo",
            "study_type": "Illustrative systematic review",
            "doi": None,
            "finding": (
                "Illustrative finding: relaxation and stress-management "
                "approaches may be relevant to student well-being."
            ),
            "limitations": (
                "Demonstration content only. No actual research "
                "has been retrieved or verified."
            ),
        },
    ],
    "support": [
        "Consider taking short breaks during study sessions.",
        "Explore relaxation techniques that feel comfortable.",
        "Seek support from trusted people or university services.",
    ],
}


# =========================================================
# Results Dashboard
# =========================================================

def render_research_results(result):

    st.divider()

    st.header(
        result_ui_text(
            "Research Results",
            "科研报告"
        )
    )

    # -----------------------------------------------------
    # Demo / Live Status
    # -----------------------------------------------------

    status = result.get("status", "unknown")

    if status == "demo":
        st.warning(
            result_ui_text(
                "DEMO MODE — The information below is illustrative. "
                "No SciencePal research task has been executed. "
                "The example studies are fictional placeholders.",
                "演示模式：以下内容仅供展示。"
                "尚未执行 SciencePal 科研任务，"
                "示例研究文献均为虚构内容。"
            )
        )

    elif status == "completed":
        st.info(
            result_ui_text(
                "Research results have been received. "
                "Individual references still require verification.",
                "已收到科研结果。"
                "其中引用的文献仍需要进一步核实。"
            )
        )

    else:
        st.error(
            result_ui_text(
                "The research result status could not be confirmed.",
                "无法确认科研报告的执行状态。"
            )
        )
        return

    # -----------------------------------------------------
    # Research Summary
    # -----------------------------------------------------

    st.subheader(
        result_ui_text(
            "Research Summary",
            "研究摘要"
        )
    )

    st.write(
        result.get("summary")
        or result_ui_text(
            "No research summary is available.",
            "暂无研究摘要。"
        )
    )

    # -----------------------------------------------------
    # Scientific Evidence
    # -----------------------------------------------------


    st.subheader(
        result_ui_text(
            "Scientific Evidence",
            "科学研究证据"
        )
    )

    papers = result.get("papers", [])

    if not papers:
        st.info(
            result_ui_text(
                "No research references are available.",
                "暂无可用的研究文献。"
            )
        )


    for index, paper in enumerate(papers, start=1):

        with st.container(border=True):

            # Paper Title
            st.markdown(
                f"### {index}. "
                f"{paper.get('title') or result_ui_text('Untitled study', '未命名文献')}"
            )

            # Authors
            st.write(
                result_ui_text("**Authors:** ", "**作者：** ")
                + str(
                    paper.get("authors")
                    or result_ui_text("Not available", "暂无")
                )
            )

            # Publication Year
            st.write(
                result_ui_text("**Year:** ", "**年份：** ")
                + str(
                    paper.get("year")
                    or result_ui_text("Not available", "暂无")
                )
            )

            # Study Type
            st.write(
                result_ui_text("**Study Type:** ", "**研究类型：** ")
                + str(
                    paper.get("study_type")
                    or result_ui_text("Not available", "暂无")
                )
            )

            # DOI
            doi = paper.get("doi")

            if doi:
                st.write(f"**DOI:** {doi}")
            else:
                st.caption(
                    result_ui_text(
                        "No verified DOI available.",
                        "暂无已核验的 DOI。"
                    )
                )

            # Key Finding
            st.markdown(
                result_ui_text(
                    "**Key Finding**",
                    "**主要研究发现**"
                )
            )

            st.write(
                paper.get("finding")
                or result_ui_text(
                    "No finding available.",
                    "暂无研究发现。"
                )
            )

            # Research Limitations
            st.markdown(
                result_ui_text(
                    "**Research Limitations**",
                    "**研究局限性**"
                )
            )

            st.write(
                paper.get("limitations")
                or result_ui_text(
                    "Limitations have not been established.",
                    "尚未明确研究局限性。"
                )
            )


    # -----------------------------------------------------
    # Educational Support
    # -----------------------------------------------------

    st.subheader(
        result_ui_text(
            "General Support Options",
            "一般支持建议"
        )
    )

    support_options = result.get("support", [])

    for option in support_options:
        st.write(f"• {option}")

    st.caption(
        result_ui_text(
            "These are general educational suggestions, "
            "not personalised treatment recommendations.",
            "以上内容仅为一般性教育建议，"
            "不构成个性化治疗建议。"
        )
    )

    st.divider()

    st.caption(
        result_ui_text(
            "MindBridge is a non-diagnostic research prototype. "
            "It has not undergone clinical validation and cannot "
            "replace professional mental health care.",
            "MindBridge 是一个不提供医学诊断的科研原型系统。"
            "本系统尚未经过临床验证，"
            "不能替代专业心理健康服务。"
        )
    )
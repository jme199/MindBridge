import streamlit as st


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

    st.header("Research Results")

    # -----------------------------------------------------
    # Demo / Live Status
    # -----------------------------------------------------

    status = result.get("status", "unknown")

    if status == "demo":
        st.warning(
            "DEMO MODE — The information below is illustrative. "
            "No SciencePal research task has been executed. "
            "The example studies are fictional placeholders."
        )

    elif status == "completed":
        st.info(
            "Research results have been received. "
            "Individual references still require verification."
        )

    else:
        st.error(
            "The research result status could not be confirmed."
        )
        return

    # -----------------------------------------------------
    # Research Summary
    # -----------------------------------------------------

    st.subheader("Research Summary")

    st.write(
        result.get(
            "summary",
            "No research summary is available."
        )
    )

    # -----------------------------------------------------
    # Scientific Evidence
    # -----------------------------------------------------

    st.subheader("Scientific Evidence")

    papers = result.get("papers", [])

    if not papers:
        st.info("No research references are available.")

    for index, paper in enumerate(papers, start=1):

        with st.container(border=True):

            st.markdown(
                f"### {index}. {paper.get('title', 'Untitled study')}"
            )

            st.write(
                f"**Authors:** {paper.get('authors', 'Not available')}"
            )

            st.write(
                f"**Year:** {paper.get('year', 'Not available')}"
            )

            st.write(
                f"**Study Type:** "
                f"{paper.get('study_type', 'Not available')}"
            )

            doi = paper.get("doi")

            if doi:
                st.write(f"**DOI:** {doi}")
            else:
                st.caption("No verified DOI available.")

            st.markdown("**Key Finding**")
            st.write(
                paper.get(
                    "finding",
                    "No finding available."
                )
            )

            st.markdown("**Research Limitations**")
            st.write(
                paper.get(
                    "limitations",
                    "Limitations have not been established."
                )
            )

    # -----------------------------------------------------
    # Educational Support
    # -----------------------------------------------------

    st.subheader("General Support Options")

    support_options = result.get("support", [])

    for option in support_options:
        st.write(f"• {option}")

    st.caption(
        "These are general educational suggestions, "
        "not personalised treatment recommendations."
    )

    st.divider()

    st.caption(
        "MindBridge is a non-diagnostic research prototype. "
        "It has not undergone clinical validation and cannot "
        "replace professional mental health care."
    )
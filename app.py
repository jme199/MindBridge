import asyncio
import logging
import streamlit as st
import threading
from concurrent.futures import ThreadPoolExecutor

from scoring import calculate_gad7

from research_results import render_research_results

from workflows.research_pipeline import run_research_pipeline
from workflows.evidence_validation import validate_research_evidence


# Clear research request and input widgets
def clear_research_request():

    # Prevent clearing an active research workflow
    if st.session_state.get("research_status") == "running":
        return

    # Clear the previous background research job
    st.session_state.pop("research_job", None)

    st.session_state.pop("research_request", None)
    st.session_state.pop("research_status", None)
    st.session_state.pop("show_demo_results", None)

    # Clear Multi-Agent workflow results
    st.session_state.pop("research_pipeline_result", None)
    st.session_state.pop("research_error", None)
    st.session_state["research_live_consent"] = False

    # Reset input widgets
    st.session_state.research_question = ""
    st.session_state.research_topic = None


# =========================================================
# 1. Page Configuration
# =========================================================

st.set_page_config(
    page_title="MindBridge | Mental Wellness",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize session state

# -----------------------------------------------------
# UI Language Configuration
# -----------------------------------------------------

if "ui_language" not in st.session_state:
    st.session_state.ui_language = "EN"


def ui_text(en, zh):
    """Return Streamlit UI text in the selected language."""
    return zh if st.session_state.ui_language == "中文" else en


if "page" not in st.session_state:
    st.session_state.page = "home"

# Initialize research background task state
if "research_job" not in st.session_state:
    st.session_state.research_job = None

# =========================================================
# Research Background Task Manager
# =========================================================

class ResearchJob:
    """
    Store the state of one background research workflow.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.future = None
        self.loop = None
        self.task = None

        self.cancel_requested = False
        self.status = "pending"

        self.agent_states = {
            "research": "Not Started",
            "verification": "Not Started",
            "explanation": "Not Started",
        }

        self.current_run_id = None
        self.current_role = None

        self.result = None
        self.error = None


@st.cache_resource(show_spinner=False)
def get_research_executor():
    """
    Reuse a thread pool across Streamlit reruns.
    """
    return ThreadPoolExecutor(
        max_workers=4,
        thread_name_prefix="mindbridge_research",
    )


# =========================================================
# Background Research Execution
# =========================================================

def execute_research_job(job, question, api_key):
    """
    Execute the research pipeline in a background thread.
    Do not call Streamlit UI functions from this thread.
    """

    async def runner():

        with job.lock:
            job.loop = asyncio.get_running_loop()
            job.task = asyncio.current_task()
            cancelled = job.cancel_requested

        if cancelled:
            raise asyncio.CancelledError()

        # Update progress without calling Streamlit
        def update_progress(role, status):
            with job.lock:
                job.agent_states[role] = status

                # Clear the previous Run ID when an Agent starts
                if status == "running":
                    job.current_role = role
                    job.current_run_id = None

                # Clear the Run ID when the Agent finishes
                elif job.current_role == role:
                    job.current_run_id = None

        # Record the currently running SciencePal Run ID

        # Record the current SciencePal Run ID
        def on_run_started(run_info):
            with job.lock:
                job.current_role = run_info["role"]
                job.current_run_id = run_info["run_id"]

                # Check if cancellation was requested
                # before the Run ID became available
                cancel_requested = job.cancel_requested
                loop = job.loop
                task = job.task

            # Cancel as soon as the Run ID is available
            if (
                cancel_requested
                and loop is not None
                and task is not None
            ):
                try:
                    loop.call_soon_threadsafe(task.cancel)
                except RuntimeError:
                    logging.warning(
                        "Research event loop is no longer available."
                    )


        # Check whether cancellation was requested
        def should_cancel():
            with job.lock:
                return job.cancel_requested

        return await run_research_pipeline(
            question=question,
            api_key=api_key,
            progress_callback=update_progress,
            on_run_started=on_run_started,
            should_cancel=should_cancel,
        )

    try:
        result = asyncio.run(runner())

        with job.lock:
            job.result = result
            job.status = "finished"

    except asyncio.CancelledError:

        with job.lock:
            job.status = "cancelled"

    except Exception as error:

        logging.exception(
            "Background research pipeline failed"
        )

        with job.lock:
            job.error = type(error).__name__
            job.status = "error"

    finally:

        with job.lock:
            job.loop = None
            job.task = None


# Initialize assessment workflow
if "assessment_step" not in st.session_state:
    st.session_state.assessment_step = "age"

# Initialize Emotional Support chat state
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if "support_mode" not in st.session_state:
    st.session_state.support_mode = "Just Listen"


# =========================================================
# GAD-7 Questionnaire Configuration
# =========================================================

GAD7_QUESTIONS = [
    "Feeling nervous, anxious or on edge",
    "Not being able to stop or control worrying",
    "Worrying too much about different things",
    "Trouble relaxing",
    "Being so restless that it is hard to sit still",
    "Becoming easily annoyed or irritable",
    "Feeling afraid as if something awful might happen"
]

GAD7_OPTIONS = {
    "Not at all": 0,
    "Several days": 1,
    "More than half the days": 2,
    "Nearly every day": 3
}

# Initialize questionnaire state
if "question_index" not in st.session_state:
    st.session_state.question_index = 0

if "gad7_answers" not in st.session_state:
    st.session_state.gad7_answers = {}

if "gad7_result" not in st.session_state:
    st.session_state.gad7_result = None


# =========================================================
# 2. Custom CSS
# =========================================================

st.html("""
<style>
    /* Background */
    .stApp {
        background:
            radial-gradient(
                circle at 85% 15%,
                #DBEAFE 0%,
                transparent 32%
            ),
            linear-gradient(
                135deg,
                #F8FBFF 0%,
                #FFFFFF 55%,
                #F1F5FF 100%
            );
    }

    /* Main container */
    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    /* Streamlit header */
    header[data-testid="stHeader"] {
        background: transparent;
    }

    /* Navigation */
    .brand {
        font-size: 25px;
        font-weight: 800;
        color: #1D4ED8;
        letter-spacing: -0.8px;
        padding-top: 5px;
    }

    .nav-caption {
        color: #64748B;
        font-size: 14px;
        text-align: right;
        padding-top: 12px;
    }

    /* Hero section */
    .hero {
        padding: 65px 20px 45px;
        text-align: center;
    }

    .hero-badge {
        display: inline-block;
        padding: 9px 18px;
        background: #E8F0FF;
        color: #2563EB;
        border-radius: 30px;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 22px;
    }

    .hero-title {
        font-size: clamp(38px, 5vw, 62px);
        font-weight: 800;
        letter-spacing: -2px;
        line-height: 1.15;
        color: #172554;
        margin-bottom: 24px;
    }

    .gradient-text {
        background: linear-gradient(
            90deg,
            #2563EB,
            #7C3AED
        );

        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-subtitle {
        font-size: 18px;
        line-height: 1.8;
        color: #64748B;
        max-width: 700px;
        margin: 0 auto 30px;
    }

    /* Section headings */
    .section-title {
        font-size: 29px;
        font-weight: 750;
        color: #1E293B;
        margin-bottom: 8px;
    }

    .section-subtitle {
        font-size: 15px;
        color: #64748B;
        margin-bottom: 24px;
    }

    /* Feature cards */
    .feature-card {
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid #E2E8F0;
        border-radius: 22px;
        padding: 32px;

        height: 400px;
        box-sizing: border-box;

        box-shadow: 0 10px 35px rgba(30, 64, 175, 0.045);
        margin-bottom: 16px;
    }

    .feature-icon {
        font-size: 32px;
        margin-bottom: 18px;
    }

    .feature-title {
        font-size: 21px;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 12px;
    }

    .feature-description {
        font-size: 15px;
        line-height: 1.8;
        color: #64748B;
    }

    /* Buttons */
    div.stButton > button {
        border-radius: 12px;
        min-height: 48px;
        font-weight: 600;
        border: 1px solid #DBEAFE;
        transition: all 0.2s ease;
    }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(
            100deg,
            #2563EB,
            #6366F1
        );
        color: white;
        border: none;
    }

    div.stButton > button:hover {
        border-color: #2563EB;
        color: #2563EB;
    }

    div.stButton > button[kind="primary"]:hover {
        color: white;
        border: none;
    }

    /* Footer */
    .footer {
        text-align: center;
        color: #94A3B8;
        font-size: 13px;
        margin-top: 65px;
        line-height: 1.8;
    }

    /* Mobile responsive */
    @media (max-width: 640px) {
        .hero {
            padding: 40px 5px 22px;
        }

        .feature-card {
            height: auto;
            min-height: 0;
            padding: 24px;
        }

        .nav-caption {
            font-size: 12px;
        }
    }
</style>
""")



# =========================================================
# 3. Navigation
# =========================================================

nav1, nav2, nav3 = st.columns([2, 3, 1])

with nav1:
    st.html("""
<div class="brand">
    ✦ MindBridge
</div>
""")

with nav2:
    st.html(f"""
<div class="nav-caption">
    {ui_text(
        "AI-Powered Mental Wellness Research",
        "AI 驱动的心理健康科研支持"
    )}
</div>
""")

with nav3:
    st.segmented_control(
        "Language",
        options=["EN", "中文"],
        key="ui_language",
        label_visibility="collapsed",
    )


# =========================================================
# 4. Home Page
# =========================================================


if st.session_state.page == "home":

    # -----------------------------------------------------
    # Hero Section
    # -----------------------------------------------------


    st.html(f"""
    <div class="hero">
        <div class="hero-badge">
            {ui_text(
                "✦ AI4SCIENCE · MULTI-AGENT RESEARCH",
                "✦ AI4SCIENCE · 多智能体科研"
            )}
        </div>

        <div class="hero-title">
            {ui_text(
                "Explore the Research.",
                "探索科学研究"
            )}<br>
            <span class="gradient-text">
                {ui_text(
                    "Examine the Evidence.",
                    "审视科研证据"
                )}
            </span>
        </div>

        <div class="hero-subtitle">
            {ui_text(
                "A multi-agent evidence verification system for "
                "university mental health research. "
                "Discover scientific studies, assess research "
                "claims, and understand findings and limitations.",
                "面向大学生心理健康研究的多智能体证据验证系统。"
                "帮助用户检索科学文献、核查研究论断，"
                "并理解研究发现及其局限性。"
            )}
        </div>
    </div>
    """)


    # -----------------------------------------------------
    # Research Question Entry
    # -----------------------------------------------------

    st.html(f"""
    <div class="section-title" style="text-align:center;">
        {ui_text(
            "Explore a Research Question",
            "探索科研问题"
        )}
    </div>
    <div class="section-subtitle" style="text-align:center;">
        {ui_text(
            "Start with a question about university students' mental wellbeing.",
            "从一个关于大学生心理健康的科研问题开始"
        )}
    </div>
    """)


    # -----------------------------------------------------
    # Example Research Questions — Bilingual
    # -----------------------------------------------------

    def select_example(question):
        st.session_state.home_research_question = question

    examples = [
        (
            "Academic Stress",
            "学业压力",
            "What evidence-based strategies help university "
            "students manage academic stress?",
            "哪些有科学证据支持的方法能够帮助大学生应对学业压力？"
        ),
        (
            "Loneliness",
            "孤独感",
            "What does research say about reducing loneliness "
            "among university students?",
            "科学研究对缓解大学生孤独感有哪些发现？"
        ),
        (
            "Sleep & Anxiety",
            "睡眠与焦虑",
            "What is the relationship between sleep quality "
            "and anxiety among university students?",
            "大学生的睡眠质量与焦虑之间存在什么关系？"
        ),
    ]

    example_columns = st.columns(3)

    for index, (label_en, label_zh, question_en, question_zh) in enumerate(examples):
        with example_columns[index]:
            st.button(
                ui_text(label_en, label_zh),
                key=f"home_example_{index}",
                on_click=select_example,
                args=(ui_text(question_en, question_zh),),
                use_container_width=True,
            )

    with st.container(border=True):

        home_question = st.text_area(
            ui_text(
                "Your Research Question",
                "你的科研问题"
            ),
            placeholder=ui_text(
                "Ask a scientific research question about "
                "university students' mental wellbeing...",
                "请输入一个关于大学生心理健康的科研问题..."
            ),
            height=120,
            key="home_research_question",
        )

        st.caption(
            ui_text(
                "Avoid entering personal identifiers or "
                "sensitive mental health information.",
                "请勿输入个人身份信息或敏感的心理健康信息。"
            )
        )

        if st.button(
            ui_text(
                "🔬 Explore Scientific Evidence →",
                "🔬 探索科学证据 →"
            ),
            key="home_research_button",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.get("research_status") == "running",
        ):

            question = home_question.strip()

            if not question:
                st.warning(
                    ui_text(
                        "Please enter a research question.",
                        "请输入一个科研问题。"
                    )
                )

            else:
                # Clear old results without calling SciencePal
                clear_research_request()

                # Populate existing Research Support workflow
                st.session_state.research_question = question

                st.session_state.research_request = {
                    "question": question,
                    "topic": None,
                }

                st.session_state.research_status = "pending"

                st.session_state.page = "research"
                st.rerun()

    # -----------------------------------------------------
    # Multi-Agent Workflow
    # -----------------------------------------------------

    st.html(f"""
    <div class="section-title"
         style="text-align:center; margin-top:45px;">
        {ui_text(
            "How MindBridge Works",
            "MindBridge 如何运作"
        )}
    </div>

    <div class="section-subtitle" style="text-align:center;">
        {ui_text(
            "Three specialized AI agents working together "
            "to investigate one research question.",
            "三个专业化 AI 智能体协同工作，"
            "共同完成科研问题的检索、验证与解释。"
        )}
    </div>
    """)

    agents = [
        (
            ui_text("01 · DISCOVER", "01 · 检索"),
            ui_text("🔎 Research Agent", "🔎 科研检索智能体"),
            ui_text(
                "Retrieves relevant scientific studies "
                "and organizes research findings.",
                "检索相关科学文献，"
                "并整理研究发现与证据信息。"
            )
        ),
        (
            ui_text("02 · VERIFY", "02 · 核查"),
            ui_text("🛡️ Verification Agent", "🛡️ 证据验证智能体"),
            ui_text(
                "Examines citations, checks claim support, "
                "and identifies uncertainties.",
                "核查文献引用与科学论断的证据支持情况，"
                "并识别研究中的不确定性。"
            )
        ),
        (
            ui_text("03 · EXPLAIN", "03 · 解释"),
            ui_text("📖 Explanation Agent", "📖 科研解释智能体"),
            ui_text(
                "Summarizes scientific evidence and "
                "communicates important limitations.",
                "总结科学证据，"
                "以易于理解的方式解释研究发现及其局限性。"
            )
        ),
    ]

    agent_columns = st.columns(3, gap="medium")

    for column, (step, name, description) in zip(
        agent_columns, agents
    ):

        with column:
            st.html(f"""
            <div style="
                background: white;
                border: 1px solid #E2E8F0;
                border-radius: 22px;
                padding: 28px;
                min-height: 205px;
                box-sizing: border-box;
                box-shadow: 0 10px 35px rgba(30,64,175,0.045);
            ">

                <div style="
                    color:#2563EB;
                    font-size:13px;
                    font-weight:700;
                    margin-bottom:16px;
                ">{step}</div>

                <div style="
                    font-size:20px;
                    font-weight:700;
                    color:#1E293B;
                    margin-bottom:14px;
                ">{name}</div>

                <div style="
                    font-size:15px;
                    line-height:1.7;
                    color:#64748B;
                ">{description}</div>

            </div>
            """)

    # -----------------------------------------------------
    # Research Report Preview
    # -----------------------------------------------------

    st.html(f"""
    <div class="section-title"
         style="text-align:center; margin-top:45px;">
        {ui_text(
            "What You'll Receive",
            "你将获得什么"
        )}
    </div>

    <div class="section-subtitle" style="text-align:center;">
        {ui_text(
            "A structured research report designed for "
            "transparency and evidence traceability.",
            "一份结构化的科研报告，"
            "帮助你清晰了解科学证据及其来源。"
        )}
    </div>
    """)

    with st.container(border=True):

        st.markdown(
            ui_text(
                "#### 📋 Evidence-Based Research Report",
                "#### 📋 基于科学证据的研究报告"
            )
        )

        preview_columns = st.columns(2)

        with preview_columns[0]:

            st.markdown(
                ui_text(
                    "**📚 Scientific References**\n\n"
                    "Relevant publications and available source details.",
                    "**📚 科学文献引用**\n\n"
                    "相关科研文献及其可获取的来源信息。"
                )
            )

            st.markdown(
                ui_text(
                    "**🛡️ Verification Status**\n\n"
                    "Agent-reported citation checks and verification scope.",
                    "**🛡️ 证据核查状态**\n\n"
                    "展示智能体报告的文献核查结果及核查范围。"
                )
            )

        with preview_columns[1]:

            st.markdown(
                ui_text(
                    "**🔍 Research Claim Assessment**\n\n"
                    "How available evidence relates to scientific claims.",
                    "**🔍 科研论断评估**\n\n"
                    "分析现有科学证据与研究论断之间的关系。"
                )
            )

            st.markdown(
                ui_text(
                    "**📖 Findings & Limitations**\n\n"
                    "Accessible explanations and unresolved uncertainties.",
                    "**📖 研究发现与局限性**\n\n"
                    "以易于理解的方式解释研究结果及尚未解决的不确定性。"
                )
            )

        st.caption(
            ui_text(
                "Report structure preview only. Actual research "
                "results depend on the studies and evidence retrieved. "
                "Agent-reported verification is not independent proof.",
                "以上仅为报告结构预览。实际研究结果取决于检索到的"
                "科学文献与证据。智能体报告的核查结果"
                "不等同于独立验证。"
            )
        )


    # -----------------------------------------------------
    # Footer — Bilingual
    # -----------------------------------------------------

    st.html(f"""
    <div class="footer">
        {ui_text(
            "MindBridge is a non-diagnostic research prototype, "
            "not a medical service.",
            "MindBridge 是一个非诊断性的科研原型系统，"
            "不提供医疗服务。"
        )}

        <br><br>

        {ui_text(
            "AI-generated scientific claims and citations "
            "may remain unverified. The system has not undergone "
            "clinical safety or effectiveness validation.",
            "AI 生成的科研论断和文献引用可能尚未经过独立验证。"
            "本系统尚未接受临床安全性或有效性验证。"
        )}

        <br><br>

        {ui_text(
            "© 2026 MindBridge · AI4Science Research Project",
            "© 2026 MindBridge · AI4Science 科研项目"
        )}
    </div>
    """)



# =========================================================
# 5. Self-Assessment Page
# =========================================================

elif st.session_state.page == "assessment":

    # Back button
    if st.button("← Back to Home", key="assessment_back"):
        st.session_state.page = "home"
        st.session_state.assessment_step = "age"
        st.rerun()

    st.html("""
<div class="section-title">🧠 Mental Health Self-Assessment</div>
<div class="section-subtitle">
    A structured, non-diagnostic anxiety screening experience.
</div>
""")

    # -----------------------------------------------------
    # Step 1: Age Confirmation
    # -----------------------------------------------------

    if st.session_state.assessment_step == "age":

        st.subheader("Step 1 · Age Confirmation")

        st.write(
            "Before starting the assessment, please confirm "
            "that you are 18 years of age or older."
        )

        st.caption(
            "This is a self-declaration only. "
            "We do not request identification documents. "
            "Please answer truthfully."
        )

        age_choice = st.radio(
            "Are you 18 years of age or older?",
            [
                "Yes, I am 18 or older",
                "No, I am under 18",
                "Prefer not to say"
            ],
            index=None,
            key="age_choice"
        )

        if st.button(
            "Continue →",
            type="primary",
            key="age_continue"
        ):

            if age_choice == "Yes, I am 18 or older":
                st.session_state.assessment_step = "consent"
                st.rerun()

            elif age_choice is None:
                st.warning("Please select an option.")

            else:
                st.info(
                    "This screening workflow is currently "
                    "designed for adults aged 18 and older. "
                    "You can still explore general mental "
                    "health information through Research Support."
                )

    # -----------------------------------------------------
    # Step 2: Informed Consent
    # -----------------------------------------------------

    elif st.session_state.assessment_step == "consent":

        st.subheader("Step 2 · Informed Consent")

        st.write(
            "Before you begin, please review the following information."
        )

        st.info(
            "**About the GAD-7 screening:**\n\n"
            "- It includes 7 questions about anxiety symptoms "
            "experienced during the past two weeks.\n"
            "- Each question has four response options, scored 0–3.\n"
            "- Participation is voluntary. You may pause or "
            "stop at any time.\n"
            "- Results are for educational and screening "
            "purposes only, not a medical diagnosis.\n"
            "- MindBridge has not undergone clinical safety "
            "or effectiveness validation."
        )

        consent = st.checkbox(
            "I understand the information above and "
            "voluntarily agree to participate.",
            key="consent_checkbox"
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "← Back",
                key="consent_back",
                use_container_width=True
            ):
                st.session_state.assessment_step = "age"
                st.rerun()

        with col2:
            if st.button(
                "Begin Assessment →",
                type="primary",
                key="consent_continue",
                use_container_width=True
            ):

                if consent:
                    st.session_state.assessment_step = "questions"
                    st.rerun()
                else:
                    st.warning(
                        "Please provide your consent before continuing."
                    )

    # -----------------------------------------------------
    # Step 3: GAD-7 Questionnaire
    # -----------------------------------------------------

    elif st.session_state.assessment_step == "questions":

        st.subheader("Step 3 · GAD-7 Questionnaire")

        question_index = st.session_state.question_index
        question_number = question_index + 1

        answers = st.session_state.gad7_answers

        # Progress information
        st.write(
            f"**Question {question_number} of 7**"
        )

        st.progress(
            len(answers) / 7
        )

        st.caption(
            f"{len(answers)} of 7 questions answered"
        )

        st.divider()

        # Display current question
        st.write(
            "**Over the last 2 weeks, how often have you "
            "been bothered by the following problem?**"
        )

        st.markdown(
            f"### {GAD7_QUESTIONS[question_index]}"
        )

        options = list(GAD7_OPTIONS.keys())

        # Recover previously selected answer if available
        previous_answer = answers.get(question_index)

        selected_index = None

        if previous_answer is not None:
            selected_index = list(
                GAD7_OPTIONS.values()
            ).index(previous_answer)

        selected_option = st.radio(
            "Select your answer:",
            options,
            index=selected_index,
            key=f"question_{question_index}"
        )

        st.divider()

        col1, col2, col3 = st.columns([1, 1, 1])

        # Previous question
        with col1:

            if st.button(
                "← Previous",
                disabled=(question_index == 0),
                use_container_width=True
            ):
                st.session_state.question_index -= 1
                st.rerun()

        # Exit assessment
        with col2:

            if st.button(
                "Exit Assessment",
                use_container_width=True
            ):
                st.session_state.assessment_step = "age"
                st.session_state.page = "home"

                st.session_state.question_index = 0
                st.session_state.gad7_answers = {}
                st.session_state.gad7_result = None

                st.rerun()

        # Next question / Submit
        with col3:

            button_label = (
                "View Results →"
                if question_index == 6
                else "Next Question →"
            )

            if st.button(
                button_label,
                type="primary",
                use_container_width=True
            ):

                if selected_option is None:
                    st.warning(
                        "Please select an answer before continuing."
                    )

                else:

                    score = GAD7_OPTIONS[selected_option]

                    # Save or update this question's answer
                    st.session_state.gad7_answers[
                        question_index
                    ] = score

                    if question_index < 6:

                        st.session_state.question_index += 1
                        st.rerun()

                    else:

                        # Verify all seven answers are present
                        if set(st.session_state.gad7_answers) != set(range(7)):
                            st.error(
                                "Some answers are missing. "
                                "Please review the questionnaire."
                            )

                        else:

                            ordered_answers = [
                                st.session_state.gad7_answers[i]
                                for i in range(7)
                            ]

                            try:

                                result = calculate_gad7(
                                    ordered_answers
                                )

                                st.session_state.gad7_result = result

                                st.session_state.assessment_step = "results"

                                st.rerun()

                            except ValueError as error:

                                st.error(
                                    f"Scoring failed: {error}"
                                )

    # -----------------------------------------------------
    # Step 4: Assessment Results
    # -----------------------------------------------------

    elif st.session_state.assessment_step == "results":

        st.subheader("Step 4 · Your Assessment Results")

        result = st.session_state.gad7_result

        if result is None:

            st.error(
                "No verified assessment result is available."
            )

        else:

            total_score = result["total_score"]
            severity = result["severity"]

            # Main result
            col1, col2 = st.columns(2)

            with col1:

                st.metric(
                    label="GAD-7 Total Score",
                    value=f"{total_score} / 21"
                )

            with col2:

                st.metric(
                    label="Symptom Severity",
                    value=severity
                )

            st.divider()

            st.subheader("Your Responses")

            response_data = []

            for i, score in enumerate(result["answers"]):

                response_data.append({
                    "Question": f"Q{i + 1}",
                    "Response": list(GAD7_OPTIONS.keys())[score],
                    "Score": score
                })

            st.dataframe(
                response_data,
                use_container_width=True,
                hide_index=True
            )

            st.divider()

            st.subheader("Understanding Your Results")

            st.info(
                f"Your GAD-7 score is **{total_score}**, "
                f"which falls within the **{severity.lower()}** range. "
                "This describes symptom severity on a screening scale. "
                "It does not establish a diagnosis."
            )

            st.warning(
                "MindBridge is a non-diagnostic research prototype. "
                "The GAD-7 cannot establish whether you have an anxiety "
                "disorder. This application has not undergone clinical "
                "safety or effectiveness validation."
            )

            st.write(
                "If anxiety symptoms are persistent, distressing, "
                "or interfere with daily life, consider speaking "
                "with a qualified mental health professional."
            )

            st.divider()

            # Research Support Entry
            st.subheader("Explore Research-Grounded Support")

            st.write(
                "Would you like to explore scientific research "
                "related to anxiety, academic stress or mental well-being?"
            )

            if st.button(
                "🔬 Explore Evidence-Based Support →",
                key="results_to_research",
                use_container_width=True
            ):
                st.session_state.page = "research"
                st.rerun()

            st.divider()

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "Start New Assessment",
                    use_container_width=True
                ):

                    st.session_state.question_index = 0
                    st.session_state.gad7_answers = {}
                    st.session_state.gad7_result = None
                    st.session_state.assessment_step = "consent"

                    # Require fresh consent
                    st.session_state.consent_checkbox = False

                    st.rerun()

            with col2:

                if st.button(
                    "Back to Home",
                    type="primary",
                    use_container_width=True
                ):

                    st.session_state.page = "home"
                    st.session_state.assessment_step = "age"

                    st.session_state.question_index = 0
                    st.session_state.gad7_answers = {}
                    st.session_state.gad7_result = None

                    st.rerun()


# =========================================================
# 6. Research Support Page
# =========================================================

elif st.session_state.page == "research":

    if st.button(
        ui_text("← Back to Home", "← 返回主页"),
        key="research_back"
    ):
        st.session_state.page = "home"
        st.rerun()

    st.html(f"""
<div class="section-title">
    🔬 {ui_text("Evidence-Based Research Support", "基于科学证据的科研支持")}
</div>
<div class="section-subtitle">
    {ui_text(
        "Explore scientific evidence related to mental well-being.",
        "探索心理健康相关的科学研究证据。"
    )}
</div>
""")



    # -----------------------------------------------------
    # Research Question
    # -----------------------------------------------------

    st.subheader(
        ui_text(
            "What would you like to explore?",
            "你想探索什么研究问题？"
        )
    )

    research_question = st.text_area(
        ui_text(
            "Describe your question or concern",
            "描述你的研究问题或关注点"
        ),
        placeholder=ui_text(
            "For example: What does scientific research say about "
            "non-pharmacological approaches to exam anxiety?",
            "例如：科学研究对缓解考试焦虑的非药物干预方法有哪些发现？"
        ),
        height=140,
        key="research_question"
    )

    st.caption(
        ui_text(
            "Avoid including names, student IDs, contact details "
            "or other identifying information.",
            "请勿包含姓名、学号、联系方式或其他可识别个人身份的信息。"
        )
    )


    st.subheader(
        ui_text(
            "Suggested Research Topics",
            "推荐研究主题"
        )
    )

    topics = [
        "Exam Anxiety",
        "Academic Stress",
        "Sleep Difficulties",
        "Mindfulness and Relaxation"
    ]

    topic_labels_zh = {
        "Exam Anxiety": "考试焦虑",
        "Academic Stress": "学业压力",
        "Sleep Difficulties": "睡眠困难",
        "Mindfulness and Relaxation": "正念与放松"
    }

    selected_topic = st.selectbox(
        ui_text(
            "Choose a topic (optional)",
            "选择研究主题（可选）"
        ),
        topics,
        index=None,
        placeholder=ui_text(
            "Select a topic",
            "选择研究主题"
        ),
        format_func=lambda topic: ui_text(
            topic,
            topic_labels_zh.get(topic, topic)
        ),
        key="research_topic"
    )


    # -----------------------------------------------------
    # Research Consent
    # -----------------------------------------------------

    st.checkbox(
        ui_text(
            "I understand that my research question will "
            "be sent to SciencePal for processing. "
            "I will not include sensitive personal information.",
            "我了解我的科研问题将发送至 SciencePal 进行处理，"
            "并承诺不包含敏感个人信息。"
        ),
        key="research_live_consent",
        disabled=st.session_state.get("research_status") == "running",
    )



    # -----------------------------------------------------
    # Run Research — Direct Submission
    # -----------------------------------------------------

    if st.button(
        ui_text(
            "🚀 Run Research",
            "🚀 开始科研检索"
        ),
        key="research_submit",
        type="primary",
        use_container_width=True,
        disabled=(
            st.session_state.get("research_status") == "running"
            or not st.session_state.get("research_live_consent", False)
        ),
    ):

        question = research_question.strip()

        topic = selected_topic

        # Validate the current input
        if not question and not topic:

            st.warning(
                ui_text(
                    "Please enter a research question or select a topic.",
                    "请输入科研问题或选择研究主题。"
                )
            )

        else:

            # Save the latest user input
            st.session_state.research_request = {
                "question": question,
                "topic": topic,
            }

            try:
                api_key = st.secrets.get("SCIENCEPAL_API_KEY")

                if not api_key:
                    raise ValueError(
                        "SciencePal API Key is not configured."
                    )

                # Construct the Research Agent prompt
                prompt = question

                if not prompt:
                    prompt = (
                        "Review scientific research evidence "
                        f"related to {topic}."
                    )

                elif topic:
                    prompt += f"\nResearch topic: {topic}"

                # Prevent duplicate background jobs
                existing_job = st.session_state.get(
                    "research_job"
                )

                if (
                    existing_job is not None
                    and existing_job.future is not None
                    and not existing_job.future.done()
                ):

                    st.warning(
                        ui_text(
                            "A research workflow is already running.",
                            "已有科研任务正在运行。"
                        )
                    )

                else:

                    # Clear previous workflow results
                    st.session_state.pop(
                        "research_pipeline_result", None
                    )
                    st.session_state.pop(
                        "research_error", None
                    )

                    # Create a new background job
                    job = ResearchJob()

                    with job.lock:
                        job.status = "running"

                    st.session_state.research_job = job

                    # Start the existing workflow
                    job.future = get_research_executor().submit(
                        execute_research_job,
                        job,
                        prompt,
                        api_key,
                    )

                    st.session_state.research_status = "running"

                    st.rerun()

            except Exception as error:

                logging.exception(
                    "Failed to start background research"
                )

                st.session_state.research_status = "error"

                st.session_state.research_error = (
                    type(error).__name__
                )

                st.rerun()


    # -----------------------------------------------------
    # Research Status
    # -----------------------------------------------------

    if st.session_state.get("research_status") in (
        "pending",
        "running",
        "completed",
        "no_evidence",
        "safety_interrupt",
        "pending_or_failed",
        "cancelled",
        "error",
    ):

        st.divider()

        # -----------------------------------------------------
        # Multi-Agent Workflow Execution
        # -----------------------------------------------------

        status = st.session_state.get("research_status")

        if status == "pending":

            st.caption(
                ui_text(
                    "Review your question above, then click Run Research.",
                    "请确认上方的科研问题，然后点击“开始科研检索”。"
                )
            )

        # -----------------------------------------------------
        # Running Workflow — Live Progress and Cancellation
        # -----------------------------------------------------

        elif status == "running":

            @st.fragment(run_every="2s")
            def show_research_progress():

                job = st.session_state.get("research_job")

                if job is None:
                    st.session_state.research_status = "error"
                    st.session_state.research_error = "MissingResearchJob"
                    st.rerun()

                # Read background state safely
                with job.lock:
                    job_status = job.status
                    agent_states = dict(job.agent_states)
                    cancel_requested = job.cancel_requested
                    result = job.result
                    error = job.error

                # Background task completed
                if job_status == "finished":

                    if isinstance(result, dict):
                        st.session_state.research_pipeline_result = result
                        st.session_state.research_status = result.get(
                            "status", "error"
                        )
                    else:
                        st.session_state.research_status = "error"
                        st.session_state.research_error = "InvalidJobResult"

                    st.rerun()

                # Cancellation confirmed locally
                if job_status == "cancelled":
                    st.session_state.research_status = "cancelled"
                    st.rerun()

                # Background task failed
                if job_status == "error":
                    st.session_state.research_status = "error"
                    st.session_state.research_error = error or "UnknownError"
                    st.rerun()

                st.subheader(
                    ui_text(
                        "Multi-Agent Research Workflow",
                        "多智能体科研工作流"
                    )
                )


                names = {
                    "research": ui_text(
                        "Research Agent", "科研检索智能体"
                    ),
                    "verification": ui_text(
                        "Verification Agent", "证据核验智能体"
                    ),
                    "explanation": ui_text(
                        "Explanation Agent", "报告解读智能体"
                    ),
                }

                status_labels_zh = {
                    "pending": "等待中",
                    "waiting": "等待中",
                    "queued": "排队中",
                    "running": "运行中",
                    "not_started": "尚未开始",
                    "completed": "已完成",
                    "finished": "已完成",
                    "failed": "执行失败",
                    "error": "发生错误",
                    "cancelled": "已取消",
                    "skipped": "已跳过",
                    "safety_interrupt": "安全中断",
                }

                progress_data = [
                    {
                        ui_text("Agent", "智能体"): name,
                        ui_text("Status", "状态"): ui_text(
                            agent_states[role],
                            status_labels_zh.get(
                                str(agent_states[role]).strip().lower().replace(" ", "_"),
                                agent_states[role]
                            )
                        ),
                    }
                    for role, name in names.items()
                ]

                st.table(progress_data)


                if cancel_requested:
                    st.warning(
                        ui_text(
                            "Cancellation requested. Waiting for "
                            "the background task to stop.",
                            "已请求取消科研任务，正在等待后台任务停止。"
                        )
                    )


                elif st.button(
                    ui_text("🛑 Cancel Research", "🛑 取消科研任务"),
                    key="cancel_live_research",
                    type="secondary",
                    use_container_width=True,
                ):

                    # Record the cancellation request
                    with job.lock:
                        job.cancel_requested = True

                        loop = job.loop
                        task = job.task
                        run_id = job.current_run_id
                        future = job.future

                    # Case 1: Background task has not started
                    if future is not None and future.cancel():
                        with job.lock:
                            job.status = "cancelled"

                    # Case 2: Remote Run ID is available
                    elif (
                        run_id is not None
                        and loop is not None
                        and task is not None
                    ):
                        try:
                            loop.call_soon_threadsafe(
                                task.cancel
                            )
                        except RuntimeError:
                            logging.warning(
                                "Research event loop is no longer available."
                            )

                    # Case 3: Run ID not yet available
                    # Keep cancel_requested=True.
                    # on_run_started() will handle cancellation
                    # once the Run ID becomes available.

                    st.rerun()

            show_research_progress()

        elif status == "cancelled":

            st.warning(
                ui_text(
                    "The local research workflow was cancelled. "
                    "Remote SciencePal cancellation may not yet "
                    "be independently confirmed.",
                    "本地科研任务已取消，但尚未独立确认 "
                    "SciencePal 远程任务是否也已取消。"
                )
            )



        # -----------------------------------------------------
        # Completed Workflow
        # -----------------------------------------------------

        elif status == "completed":

            st.success(
                ui_text(
                    "The Multi-Agent Research Workflow has completed.",
                    "多智能体科研工作流已完成。"
                )
            )

            st.write(
                ui_text(
                    "Research, verification and explanation results "
                    "have been received.",
                    "已收到科研检索、证据核验和报告解读结果。"
                )
            )

            st.caption(
                ui_text(
                    "The final report will be displayed below "
                    "if the validation checks pass.",
                    "如果报告通过验证检查，最终科研报告将在下方显示。"
                )
            )


        # -----------------------------------------------------
        # Safety Interrupt
        # -----------------------------------------------------

        elif status == "safety_interrupt":

            result = st.session_state.get(
                "research_pipeline_result"
            ) or {}

            safety_message = result.get("safety_message")

            if not isinstance(safety_message, str) or not safety_message.strip():
                safety_message = (
                    "An urgent safety concern was identified. "
                    "Please seek immediate assistance from local "
                    "emergency services or a trusted person."
                )

            st.error(
                ui_text(
                    "Safety Alert",
                    "安全提醒"
                )
            )

            st.warning(safety_message)

            st.info(
                ui_text(
                    "The research workflow was stopped for safety. "
                    "Verification and Explanation Agents were not started.",
                    "出于安全考虑，科研工作流已停止。"
                    "证据核验智能体和报告解读智能体均未启动。"
                )
            )


        # -----------------------------------------------------
        # No Evidence
        # -----------------------------------------------------

        elif status == "no_evidence":

            st.info(
                ui_text(
                    "The Research Agent did not return studies "
                    "for the next verification stage.",
                    "科研检索智能体未返回可供下一阶段核验的研究文献。"
                )
            )

        # -----------------------------------------------------
        # Incomplete or Failed Workflow
        # -----------------------------------------------------

        elif status == "pending_or_failed":

            result = st.session_state.get(
                "research_pipeline_result", {}
            )

            failed_stage = result.get(
                "stage", "unknown"
            )

            st.warning(
                ui_text(
                    f"The workflow did not complete at "
                    f"the {failed_stage} stage.",
                    f"科研工作流在 {failed_stage} 阶段未完成。"
                )
            )

        # -----------------------------------------------------
        # API or Processing Error
        # -----------------------------------------------------

        elif status == "error":

            error_type = st.session_state.get(
                "research_error", "UnknownError"
            )

            st.error(
                ui_text(
                    "The research workflow encountered an error. "
                    f"Error type: {error_type}.",
                    "科研工作流执行过程中发生错误。"
                    f"错误类型：{error_type}。"
                )
            )

        # -----------------------------------------------------
        # Agent Execution Status Dashboard
        # -----------------------------------------------------

        pipeline_result = st.session_state.get(
            "research_pipeline_result"
        )

        if pipeline_result:

            st.divider()

            st.subheader(
                ui_text(
                    "Multi-Agent Execution Status",
                    "多智能体执行状态"
                )
            )

            # Retrieve Agent run records
            run_history = pipeline_result.get("runs", [])

            run_statuses = {
                run["role"]: run["status"]
                for run in run_history
            }


            # Define Agent execution order
            agent_stages = [
                (
                    "research",
                    ui_text("Research Agent", "科研检索智能体")
                ),
                (
                    "verification",
                    ui_text("Verification Agent", "证据核验智能体")
                ),
                (
                    "explanation",
                    ui_text("Explanation Agent", "报告解读智能体")
                ),
            ]

            # Display labels for Agent execution statuses
            status_labels = {
                "completed": ui_text("✅ Completed", "✅ 已完成"),
                "running": ui_text("⏳ Running", "⏳ 运行中"),
                "asked": ui_text(
                    "⏸️ Waiting for Input", "⏸️ 等待输入"
                ),
                "failed": ui_text("❌ Failed", "❌ 执行失败"),
                "stopped": ui_text("⏹️ Stopped", "⏹️ 已停止"),
                "timed_out": ui_text("⌛ Timed Out", "⌛ 已超时"),
            }

            status_data = []

            for role, agent_name in agent_stages:

                agent_status = run_statuses.get(
                    role, "not_started"
                )

                display_status = status_labels.get(
                    agent_status,
                    ui_text("⚪ Not Started", "⚪ 尚未开始")
                    if agent_status == "not_started"
                    else f"⚠️ {agent_status}"
                )

                status_data.append({
                    ui_text("Agent", "智能体"): agent_name,
                    ui_text("Status", "状态"): display_status
                })

            # Display Agent status table
            st.table(status_data)

            st.caption(
                ui_text(
                    "Completed means the Agent run finished. "
                    "It does not guarantee that the scientific "
                    "evidence or citations have been independently "
                    "validated.",
                    "已完成仅表示智能体运行结束，"
                    "不代表科学证据或引用文献已经过独立核实。"
                )
            )

        # -----------------------------------------------------
        # Live Research Results
        # -----------------------------------------------------

        if st.session_state.get("research_status") == "completed":

            pipeline_result = st.session_state.get(
                "research_pipeline_result"
            ) or {}

            # Extract Explanation Agent output
            report = pipeline_result.get("result")

            if not isinstance(report, dict):

                st.error(
                    ui_text(
                        "The Explanation Agent did not return "
                        "a valid research report.",
                        "报告解读智能体未返回有效的科研报告。"
                    )
                )

            elif (
                not isinstance(report.get("summary"), str)
                or not report["summary"].strip()
                or not isinstance(report.get("papers"), list)
                or not all(
                    isinstance(paper, dict)
                    for paper in report["papers"]
                )
            ):

                st.error(
                    ui_text(
                        "The research report is incomplete "
                        "or has an invalid structure.",
                        "科研报告内容不完整或数据结构不符合要求。"
                    )
                )

            else:

                st.warning(
                    ui_text(
                        "This report was generated by AI Agents. "
                        "Individual research claims, publication "
                        "details and citations require independent "
                        "verification before being relied upon.",
                        "本报告由 AI 智能体生成。"
                        "在采信报告内容之前，应独立核实具体科研结论、"
                        "论文出版信息及引用文献。"
                    )
                )

                # Prepare data for the existing dashboard
                display_report = report.copy()

                display_report["status"] = "completed"

                support = report.get("support", [])

                display_report["support"] = (
                    [
                        item
                        for item in support
                        if isinstance(item, str)
                    ]
                    if isinstance(support, list)
                    else []
                )

                # -----------------------------------------------------
                # Evidence Validation
                # -----------------------------------------------------

                try:

                    evidence_audit = validate_research_evidence(
                        pipeline_result
                    )

                except (ValueError, TypeError, AttributeError):

                    st.error(
                        ui_text(
                            "Evidence cross-check could not be completed. "
                            "The research report has not been displayed.",
                            "证据一致性检查未能完成，"
                            "因此暂未展示科研报告。"
                        )
                    )

                else:

                    st.divider()

                    st.subheader(
                        ui_text(
                            "Agent Evidence Consistency Check",
                            "智能体间证据一致性检查"
                        )
                    )

                    st.info(
                        ui_text(
                            "This check compares study IDs between the "
                            "Verification and Explanation Agents. "
                            "It does not directly query external databases "
                            "or independently verify DOI records, "
                            "publication metadata, or research claims.",
                            "此检查用于比对证据核验智能体与报告解读智能体"
                            "输出的研究文献 ID 是否一致。"
                            "该环节不会直接查询外部数据库，"
                            "也不会独立核验 DOI 记录、出版信息或科研结论。"
                        )
                    )

                    # ---------------------------------------------
                    # Evidence Summary
                    # ---------------------------------------------


                    st.write(
                        ui_text(
                            "**Total References:** ",
                            "**文献总数：** "
                        )
                        + str(evidence_audit["total_papers"])
                    )

                    st.write(
                        ui_text(
                            "**References marked verified by Agent:** ",
                            "**智能体标记为已核验的文献数：** "
                        )
                        + str(evidence_audit["agent_verified_papers"])
                    )


                    # ---------------------------------------------
                    # Paper Verification Status
                    # ---------------------------------------------

                    evidence_records = evidence_audit.get(
                        "evidence_records", []
                    )


                    if evidence_records:

                        evidence_table = []

                        for record in evidence_records:

                            verification_status = record.get(
                                "verification_status"
                            )

                            if (
                                verification_status
                                == "agent_reported_verified"
                            ):

                                status_text = ui_text(
                                    "Agent-reported metadata verified",
                                    "智能体报告元数据已核验"
                                )

                            else:

                                status_text = ui_text(
                                    "Not confirmed",
                                    "尚未确认"
                                )

                            evidence_table.append({
                                ui_text("Study ID", "文献 ID"): (
                                    record.get("study_id")
                                    or ui_text("Not available", "暂无")
                                ),
                                ui_text("Paper", "文献"): (
                                    record.get("title")
                                    or ui_text("Untitled study", "未命名文献")
                                ),
                                ui_text(
                                    "Verification Status", "核验状态"
                                ): status_text,
                            })

                        st.dataframe(
                            evidence_table,
                            use_container_width=True,
                            hide_index=True
                        )


                    else:

                        st.info(
                            ui_text(
                                "No research references are available "
                                "for cross-checking.",
                                "暂无可用于交叉检查的研究文献。"
                            )
                        )

                    # ---------------------------------------------
                    # Claim Assessment
                    # ---------------------------------------------

                    claim_records = evidence_audit.get(
                        "claim_records", []
                    )


                    if claim_records:

                        st.subheader(
                            ui_text(
                                "Research Claim Assessment",
                                "科研论断评估"
                            )
                        )

                        claim_table = []

                        for claim in claim_records:

                            claim_table.append({
                                ui_text(
                                    "Claim ID", "论断 ID"
                                ): (
                                    claim.get("claim_id")
                                    or ui_text("Not available", "暂无")
                                ),
                                ui_text(
                                    "Agent-Reported Support",
                                    "智能体报告的证据支持情况"
                                ): (
                                    claim.get("support_status")
                                    or ui_text("Not reported", "未报告")
                                ),
                            })

                        st.dataframe(
                            claim_table,
                            use_container_width=True,
                            hide_index=True
                        )

                    st.caption(
                        ui_text(
                            "Verification statuses and claim assessments "
                            "are generated by AI Agents. "
                            "A matching study ID is not proof that "
                            "a publication exists or supports a claim.",
                            "文献核验状态和科研论断评估由 AI 智能体生成。"
                            "文献 ID 一致并不能证明该论文真实存在，"
                            "也不能证明该论文支持相应的科研论断。"
                        )
                    )

                    # ---------------------------------------------
                    # Display Research Results
                    # ---------------------------------------------

                    render_research_results(display_report)


        st.button(
            ui_text("Clear Request", "清除科研问题"),
            key="clear_research",
            on_click=clear_research_request,
            disabled=st.session_state.get("research_status") == "running"
        )




# =========================================================
# 7. Emotional Support Page
# =========================================================

elif st.session_state.page == "emotional":

    if st.button("← Back to Home", key="emotional_back"):
        st.session_state.page = "home"
        st.rerun()

    st.html("""
<div class="section-title">💬 Emotional Support</div>
<div class="section-subtitle">
    A supportive space to share what's on your mind.
</div>
""")

    st.info(
        "MindBridge offers non-diagnostic emotional support. "
        "It is not a therapist or emergency service. "
        "This feature is currently under development."
    )

    # Support mode
    st.subheader("How would you like to be supported?")

    st.selectbox(
        "Choose your preferred support style",
        [
            "Just Listen",
            "Help Me Reflect",
            "Suggest Strategies"
        ],
        key="support_mode"
    )

    st.divider()

    # Chat history
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # Chat input
    user_message = st.chat_input(
        "Share what's on your mind..."
    )

    if user_message:

        st.session_state.chat_messages.append({
            "role": "user",
            "content": user_message
        })

        st.rerun()

    st.warning(
        "SciencePal Agent API is not connected yet. "
        "Messages are displayed locally, but no AI response "
        "is currently generated."
    )

    if st.button("Clear Conversation", key="clear_chat"):
        st.session_state.chat_messages = []
        st.rerun()
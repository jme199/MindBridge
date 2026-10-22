import asyncio
import logging
import streamlit as st
import threading
from concurrent.futures import ThreadPoolExecutor

from scoring import calculate_gad7

from research_results import (
    DEMO_RESEARCH_RESULT,
    render_research_results
)

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
    st.session_state.pop("research_live_consent", None)

    # Reset input widgets
    st.session_state.research_question = ""
    st.session_state.research_topic = "Select a topic"


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

nav1, nav2 = st.columns([2, 3])

with nav1:
    st.html("""
<div class="brand">
    ✦ MindBridge
</div>
""")

with nav2:
    st.html("""
<div class="nav-caption">
    AI-Powered Mental Wellness Research
</div>
""")


# =========================================================
# 4. Home Page
# =========================================================


if st.session_state.page == "home":

    # -----------------------------------------------------
    # Hero Section
    # -----------------------------------------------------

    st.html("""
    <div class="hero">
        <div class="hero-badge">
            ✦ AI4SCIENCE · MULTI-AGENT RESEARCH
        </div>

        <div class="hero-title">
            Explore the Research.<br>
            <span class="gradient-text">
                Examine the Evidence.
            </span>
        </div>

        <div class="hero-subtitle">
            A multi-agent evidence verification system for
            university mental health research.
            Discover scientific studies, assess research
            claims, and understand findings and limitations.
        </div>
    </div>
    """)

    # -----------------------------------------------------
    # Research Question Entry
    # -----------------------------------------------------

    st.html("""
    <div class="section-title" style="text-align:center;">
        Explore a Research Question
    </div>
    <div class="section-subtitle" style="text-align:center;">
        Start with a question about university students'
        mental wellbeing.
    </div>
    """)

    # Example question callback
    def select_example(question):
        st.session_state.home_research_question = question

    examples = [
        (
            "Academic Stress",
            "What evidence-based strategies help university "
            "students manage academic stress?"
        ),
        (
            "Loneliness",
            "What does research say about reducing loneliness "
            "among university students?"
        ),
        (
            "Sleep & Anxiety",
            "What is the relationship between sleep quality "
            "and anxiety among university students?"
        ),
    ]

    example_columns = st.columns(3)

    for index, (label, question) in enumerate(examples):
        with example_columns[index]:
            st.button(
                label,
                key=f"home_example_{index}",
                on_click=select_example,
                args=(question,),
                use_container_width=True,
            )

    with st.container(border=True):

        home_question = st.text_area(
            "Your Research Question",
            placeholder=(
                "Ask a scientific research question about "
                "university students' mental wellbeing..."
            ),
            height=120,
            key="home_research_question",
        )

        st.caption(
            "Avoid entering personal identifiers or "
            "sensitive mental health information."
        )

        if st.button(
            "🔬 Explore Scientific Evidence →",
            key="home_research_button",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.get("research_status") == "running",
        ):

            question = home_question.strip()

            if not question:
                st.warning("Please enter a research question.")

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

    st.html("""
    <div class="section-title"
         style="text-align:center; margin-top:45px;">
        How MindBridge Works
    </div>

    <div class="section-subtitle" style="text-align:center;">
        Three specialized AI agents working together
        to investigate one research question.
    </div>
    """)

    agents = [
        (
            "01 · DISCOVER",
            "🔎 Research Agent",
            "Retrieves relevant scientific studies "
            "and organizes research findings."
        ),
        (
            "02 · VERIFY",
            "🛡️ Verification Agent",
            "Examines citations, checks claim support, "
            "and identifies uncertainties."
        ),
        (
            "03 · EXPLAIN",
            "📖 Explanation Agent",
            "Summarizes scientific evidence and "
            "communicates important limitations."
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

    st.html("""
    <div class="section-title"
         style="text-align:center; margin-top:45px;">
        What You'll Receive
    </div>

    <div class="section-subtitle" style="text-align:center;">
        A structured research report designed for
        transparency and evidence traceability.
    </div>
    """)

    with st.container(border=True):

        st.markdown("#### 📋 Evidence-Based Research Report")

        preview_columns = st.columns(2)

        with preview_columns[0]:
            st.markdown(
                "**📚 Scientific References**\n\n"
                "Relevant publications and available source details."
            )

            st.markdown(
                "**🛡️ Verification Status**\n\n"
                "Agent-reported citation checks and verification scope."
            )

        with preview_columns[1]:
            st.markdown(
                "**🔍 Research Claim Assessment**\n\n"
                "How available evidence relates to scientific claims."
            )

            st.markdown(
                "**📖 Findings & Limitations**\n\n"
                "Accessible explanations and unresolved uncertainties."
            )

        st.caption(
            "Report structure preview only. Actual research "
            "results depend on the studies and evidence retrieved. "
            "Agent-reported verification is not independent proof."
        )

    # -----------------------------------------------------
    # Footer
    # -----------------------------------------------------

    st.html("""
    <div class="footer">
        MindBridge is a non-diagnostic research prototype,
        not a medical service.<br>

        AI-generated scientific claims and citations
        may remain unverified. The system has not undergone
        clinical safety or effectiveness validation.

        <br><br>

        © 2026 MindBridge · AI4Science Research Project
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

    if st.button("← Back to Home", key="research_back"):
        st.session_state.page = "home"
        st.rerun()

    st.html("""
<div class="section-title">
    🔬 Evidence-Based Research Support
</div>
<div class="section-subtitle">
    Explore scientific evidence related to mental well-being.
</div>
""")

    st.info(
        "MindBridge helps university students explore scientific "
        "research on anxiety, academic stress, sleep and mental "
        "well-being. Information is educational and non-diagnostic."
    )

    # -----------------------------------------------------
    # Research Question
    # -----------------------------------------------------

    st.subheader("What would you like to explore?")

    research_question = st.text_area(
        "Describe your question or concern",
        placeholder=(
            "For example: What does scientific research say about "
            "non-pharmacological approaches to exam anxiety?"
        ),
        height=140,
        key="research_question"
    )

    st.caption(
        "Avoid including names, student IDs, contact details "
        "or other identifying information."
    )

    st.subheader("Suggested Research Topics")

    topics = [
        "Exam Anxiety",
        "Academic Stress",
        "Sleep Difficulties",
        "Mindfulness and Relaxation"
    ]

    selected_topic = st.selectbox(
        "Choose a topic (optional)",
        ["Select a topic"] + topics,
        key="research_topic"
    )

    # -----------------------------------------------------
    # Submit
    # -----------------------------------------------------

    if st.button(
        "🔬 Explore Scientific Evidence →",
        type="primary",
        use_container_width=True,
        key="research_submit",
        disabled=st.session_state.get("research_status") == "running",
    ):

        if (
            not research_question.strip()
            and selected_topic == "Select a topic"
        ):

            st.warning(
                "Please enter a research question or select a topic."
            )

        else:

            # Save the research request
            st.session_state.research_request = {
                "question": research_question.strip(),
                "topic": (
                    selected_topic
                    if selected_topic != "Select a topic"
                    else None
                )
            }

            # Reset previous results
            st.session_state.pop(
                "research_pipeline_result", None
            )

            st.session_state.pop(
                "research_error", None
            )

            st.session_state.pop(
                "research_live_consent", None
            )

            # Prepare request without calling the API
            st.session_state.research_status = "pending"

    # -----------------------------------------------------
    # Research Status
    # -----------------------------------------------------

    if st.session_state.get("research_status") in (
        "pending",
        "running",
        "completed",
        "no_evidence",
        "pending_or_failed",
        "cancelled",
        "error",
    ):

        st.divider()

        st.subheader("Research Request")

        request = st.session_state.research_request

        if request["question"]:
            st.write("**Your question:**")
            st.write(request["question"])

        if request["topic"]:
            st.write(f"**Selected topic:** {request['topic']}")

        # -----------------------------------------------------
        # Multi-Agent Workflow Execution
        # -----------------------------------------------------

        status = st.session_state.get("research_status")

        if status == "pending":

            st.info(
                "Your research request is ready. "
                "No SciencePal API call has been made yet."
            )

            st.subheader("Multi-Agent Research Workflow")

            st.write("1. Research Agent — Discover relevant studies.")
            st.write("2. Verification Agent — Check research evidence.")
            st.write("3. Explanation Agent — Generate the final report.")

            st.checkbox(
                "I understand that my research question will "
                "be sent to SciencePal for processing. "
                "I will not include sensitive personal information.",
                key="research_live_consent"
            )


            if st.button(
                "🚀 Run Live Research",
                key="research_run_live",
                type="primary",
                use_container_width=True,
                disabled=not st.session_state.get(
                    "research_live_consent", False
                ),
            ):

                try:
                    api_key = st.secrets.get(
                        "SCIENCEPAL_API_KEY"
                    )

                    if not api_key:
                        raise ValueError(
                            "SciencePal API Key is not configured."
                        )

                    request = st.session_state.research_request

                    # Construct the Agent prompt
                    prompt = request["question"]

                    if not prompt:
                        prompt = (
                            "Review scientific research evidence "
                            f"related to {request['topic']}."
                        )

                    elif request["topic"]:
                        prompt += (
                            f"\nResearch topic: {request['topic']}"
                        )

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
                            "A research workflow is already running."
                        )

                    else:
                        # Clear results from the previous workflow
                        st.session_state.pop("research_pipeline_result", None)
                        st.session_state.pop("research_error", None)

                        # Create a background research job
                        job = ResearchJob()

                        with job.lock:
                            job.status = "running"

                        # Save the job before starting it
                        st.session_state.research_job = job

                        # Start the background workflow
                        job.future = get_research_executor().submit(
                            execute_research_job,
                            job,
                            prompt,
                            api_key,
                        )

                        st.session_state.research_status = "running"

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

                st.subheader("Multi-Agent Research Workflow")

                names = {
                    "research": "Research Agent",
                    "verification": "Verification Agent",
                    "explanation": "Explanation Agent",
                }

                progress_data = [
                    {
                        "Agent": name,
                        "Status": agent_states[role],
                    }
                    for role, name in names.items()
                ]

                st.table(progress_data)

                if cancel_requested:
                    st.warning(
                        "Cancellation requested. Waiting for "
                        "the background task to stop."
                    )


                elif st.button(
                    "🛑 Cancel Research",
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


                    with job.lock:
                        job.cancel_requested = True
                        loop = job.loop
                        task = job.task
                        future = job.future

                    # Cancel the active asyncio task safely
                    if loop is not None and task is not None:
                        try:
                            loop.call_soon_threadsafe(task.cancel)
                        except RuntimeError:
                            logging.warning(
                                "Research event loop is no longer available."
                            )

                    # Cancel a job that has not started yet
                    elif future is not None and future.cancel():
                        with job.lock:
                            job.status = "cancelled"

                    st.rerun()

            show_research_progress()

        elif status == "cancelled":

            st.warning(
                "The local research workflow was cancelled. "
                "Remote SciencePal cancellation may not yet "
                "be independently confirmed."
            )



        # -----------------------------------------------------
        # Completed Workflow
        # -----------------------------------------------------

        elif status == "completed":

            st.success(
                "The Multi-Agent Research Workflow has completed."
            )

            st.write(
                "Research, verification and explanation results "
                "have been received."
            )

            st.caption(
                "The final evidence report will be displayed "
                "after additional output validation is implemented."
            )

        # -----------------------------------------------------
        # No Evidence
        # -----------------------------------------------------

        elif status == "no_evidence":

            st.info(
                "The Research Agent did not return studies "
                "for the next verification stage."
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
                f"The workflow did not complete at "
                f"the {failed_stage} stage."
            )

        # -----------------------------------------------------
        # API or Processing Error
        # -----------------------------------------------------

        elif status == "error":

            error_type = st.session_state.get(
                "research_error", "UnknownError"
            )

            st.error(
                "The research workflow encountered an error. "
                f"Error type: {error_type}."
            )

        # -----------------------------------------------------
        # Agent Execution Status Dashboard
        # -----------------------------------------------------

        pipeline_result = st.session_state.get(
            "research_pipeline_result"
        )

        if pipeline_result:

            st.divider()

            st.subheader("Multi-Agent Execution Status")

            # Retrieve Agent run records
            run_history = pipeline_result.get("runs", [])

            run_statuses = {
                run["role"]: run["status"]
                for run in run_history
            }

            # Define Agent execution order
            agent_stages = [
                ("research", "Research Agent"),
                ("verification", "Verification Agent"),
                ("explanation", "Explanation Agent"),
            ]

            # Convert execution status into readable labels
            status_labels = {
                "completed": "✅ Completed",
                "running": "⏳ Running",
                "asked": "⏸️ Waiting for Input",
                "failed": "❌ Failed",
                "stopped": "⏹️ Stopped",
                "timed_out": "⌛ Timed Out",
            }

            status_data = []

            for role, agent_name in agent_stages:

                agent_status = run_statuses.get(
                    role, "not_started"
                )

                display_status = status_labels.get(
                    agent_status,
                    "⚪ Not Started"
                    if agent_status == "not_started"
                    else f"⚠️ {agent_status}"
                )

                status_data.append({
                    "Agent": agent_name,
                    "Status": display_status
                })

            # Display Agent status table
            st.table(status_data)

            st.caption(
                "Completed means the Agent run finished. "
                "It does not guarantee that the scientific "
                "evidence or citations have been independently "
                "validated."
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
                    "The Explanation Agent did not return "
                    "a valid research report."
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
                    "The research report is incomplete "
                    "or has an invalid structure."
                )

            else:

                st.warning(
                    "This report was generated by AI Agents. "
                    "Individual research claims, publication "
                    "details and citations require independent "
                    "verification before being relied upon."
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
                        "Evidence cross-check could not be completed. "
                        "The research report has not been displayed."
                    )

                else:

                    st.divider()

                    st.subheader("Evidence Cross-Check")

                    st.info(
                        "This check compares study IDs across "
                        "the Verification and Explanation Agents. "
                        "It does not independently verify DOI records, "
                        "publication metadata or research claims."
                    )

                    # ---------------------------------------------
                    # Evidence Summary
                    # ---------------------------------------------

                    st.write(
                        "**Total References:** "
                        f"{evidence_audit['total_papers']}"
                    )

                    st.write(
                        "**References marked verified by Agent:** "
                        f"{evidence_audit['agent_verified_papers']}"
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

                                status_text = (
                                    "Agent-reported metadata verified"
                                )

                            else:

                                status_text = "Not confirmed"

                            evidence_table.append({
                                "Study ID": (
                                    record.get("study_id")
                                    or "Not available"
                                ),
                                "Paper": record.get(
                                    "title", "Untitled study"
                                ),
                                "Verification Status": status_text,
                            })

                        st.dataframe(
                            evidence_table,
                            use_container_width=True,
                            hide_index=True
                        )

                    else:

                        st.info(
                            "No research references are available "
                            "for cross-checking."
                        )

                    # ---------------------------------------------
                    # Claim Assessment
                    # ---------------------------------------------

                    claim_records = evidence_audit.get(
                        "claim_records", []
                    )

                    if claim_records:

                        st.subheader("Research Claim Assessment")

                        claim_table = []

                        for claim in claim_records:

                            claim_table.append({
                                "Claim ID": claim.get(
                                    "claim_id", "Not available"
                                ),
                                "Agent-Reported Support": claim.get(
                                    "support_status", "Not reported"
                                ),
                            })

                        st.dataframe(
                            claim_table,
                            use_container_width=True,
                            hide_index=True
                        )

                    st.caption(
                        "Verification statuses and claim assessments "
                        "are generated by AI Agents. "
                        "A matching study ID is not proof that "
                        "a publication exists or supports a claim."
                    )

                    # ---------------------------------------------
                    # Display Research Results
                    # ---------------------------------------------

                    render_research_results(display_report)


        st.button(
            "Clear Request",
            key="clear_research",
            on_click=clear_research_request
        )

        st.divider()

        st.subheader("Research Results Preview")

        st.caption(
            "Preview the results dashboard using fictional "
            "demonstration data. No SciencePal API call is made."
        )

        if st.button(
            "Preview Demo Research Results →",
            key="preview_demo_results",
            width="stretch"
        ):
            st.session_state.show_demo_results = True
            st.rerun()

        if st.session_state.get("show_demo_results", False):
            render_research_results(DEMO_RESEARCH_RESULT)


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
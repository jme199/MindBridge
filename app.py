import streamlit as st
from scoring import calculate_gad7

from research_results import (
    DEMO_RESEARCH_RESULT,
    render_research_results
)


# Clear research request and input widgets
def clear_research_request():
    st.session_state.pop("research_request", None)
    st.session_state.pop("research_status", None)
    st.session_state.pop("show_demo_results", None)

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
        ✦ SCIENCE-POWERED MENTAL WELLNESS
    </div>

    <div class="hero-title">
        Understand Your Mind.<br>
        <span class="gradient-text">
            Empower Your Well-being.
        </span>
    </div>

    <div class="hero-subtitle">
        A bridge between mental wellness and scientific evidence.
        Explore structured self-assessment and research-grounded
        support designed for university students.
    </div>

</div>
""")

    # -----------------------------------------------------
    # Section Heading
    # -----------------------------------------------------

    st.html("""
<div class="section-title">
    How can we support you?
</div>

<div class="section-subtitle">
    Choose the path that best fits your needs.
</div>
""")

    # -----------------------------------------------------
    # Feature Cards
    # -----------------------------------------------------

    col1, col2, col3 = st.columns(3, gap="medium")

    # Emotional Support Card
    with col1:
        
    
        st.html("""
<div class="feature-card">
    <div class="feature-icon">💬</div>
    
    <div class="feature-title">
        Emotional Support
    </div>
    
    <div class="feature-description">
        Share your thoughts in a supportive,
        non-judgmental space.
    
        <br><br>
    
        Choose whether you would like someone to listen,
        help you reflect, or explore coping strategies.
    </div>
</div>
""")
    
        if st.button(
            "Start Support Chat →",
            key="emotional_button",
            type="primary",
            use_container_width=True
        ):
            st.session_state.page = "emotional"
            st.rerun()

    # Self-Assessment Card
    with col2:

        st.html("""
<div class="feature-card">

    <div class="feature-icon">
        🧠
    </div>

    <div class="feature-title">
        Mental Health Self-Assessment
    </div>

    <div class="feature-description">
        Explore your anxiety symptoms through a structured
        GAD-7 screening questionnaire.

        <br><br>

        Receive a clear, non-diagnostic interpretation
        of your responses.
    </div>

</div>
""")

        if st.button(
            "Start Self-Assessment →",
            key="assessment_button",
            type="primary",
            use_container_width=True
        ):
            st.session_state.page = "assessment"
            st.rerun()

    # Research Support Card
    with col3:

        st.html("""
<div class="feature-card">

    <div class="feature-icon">
        🔬
    </div>

    <div class="feature-title">
        Evidence-Based Research Support
    </div>

    <div class="feature-description">
        Explore scientific research related to academic
        stress, anxiety and mental well-being.

        <br><br>

        Discover research findings, credible sources
        and their limitations.
    </div>

</div>
""")

        if st.button(
            "Explore Research →",
            key="research_button",
            type="primary",
            use_container_width=True
        ):
            st.session_state.page = "research"
            st.rerun()
    
    # -----------------------------------------------------
    # Footer
    # -----------------------------------------------------

    st.html("""
<div class="footer">
    MindBridge is a non-diagnostic research prototype,
    not a medical service.<br>

    It has not undergone clinical safety or effectiveness
    validation and cannot replace professional mental
    health care.

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
        key="research_submit"
    ):

        if not research_question.strip() and selected_topic == "Select a topic":
            st.warning(
                "Please enter a research question or select a topic."
            )

        else:
            st.session_state.research_request = {
                "question": research_question.strip(),
                "topic": (
                    selected_topic
                    if selected_topic != "Select a topic"
                    else None
                )
            }

            st.session_state.research_status = "pending"

    # -----------------------------------------------------
    # Research Status
    # -----------------------------------------------------

    if st.session_state.get("research_status") == "pending":

        st.divider()

        st.subheader("Research Request")

        request = st.session_state.research_request

        if request["question"]:
            st.write("**Your question:**")
            st.write(request["question"])

        if request["topic"]:
            st.write(f"**Selected topic:** {request['topic']}")

        st.warning(
            "SciencePal Agent API integration is not yet active. "
            "Your request has been prepared locally but has not "
            "been sent to SciencePal."
        )

        st.subheader("Planned Research Workflow")

        st.write("1. Search relevant peer-reviewed literature.")
        st.write("2. Verify publication details and source links.")
        st.write("3. Extract research findings and limitations.")
        st.write("4. Present evidence-grounded educational information.")

        st.caption(
            "These steps describe the planned workflow; "
            "they have not been executed for this request."
        )

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
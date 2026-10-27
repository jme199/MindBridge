# MindBridge

### An Evidence-Grounded Multi-Agent System for University Mental Health Research

**MindBridge** is an AI-powered multi-agent research support system designed to make mental health scientific information more reliable, verifiable, and accessible to university students.

Built with **SciencePal Multi-Agent, Python, and Streamlit**, MindBridge integrates scientific literature retrieval, independent evidence verification, and accessible explanations into a structured workflow.

The project explores whether explicit evidence verification and workflow-level safety constraints can improve the reliability of LLM-generated mental health research information.

**GitHub Repository:** https://github.com/jme199/MindBridge

---

## 1. Background & Motivation

Large Language Models (LLMs) have made mental health information increasingly accessible. However, fluent and convincing responses do not always reflect scientific accuracy.

Mental health research presents several important challenges:

- **Conceptual ambiguity:** Models may confuse depressive symptoms, major depressive disorder (MDD), and other clinical conditions.
- **Differences in evidence quality:** Randomized controlled trials, cross-sectional surveys, and clinical studies provide different levels of evidence.
- **Citation hallucinations:** Models may generate fabricated references or attribute unsupported claims to genuine publications.
- **Limited accessibility:** University students may struggle to verify scientific references or interpret complex research findings independently.

MindBridge addresses these challenges through a structured multi-agent approach that separates evidence retrieval, verification, and explanation.

**The central idea is that multiple agents do not necessarily provide greater intelligence, but clearly defined responsibilities and verification constraints may improve reliability.**

## 2. Key Features

### 2.1 Scientific Literature Retrieval

The **Research Agent** uses a custom-developed Skill connected to the **Europe PMC API** to retrieve relevant scientific literature.

This enables the system to access external research information rather than relying exclusively on the LLM's internal knowledge.

### 2.2 Independent Evidence Verification

The **Verification Agent** uses a custom-developed Skill to evaluate scientific evidence and identify potential problems, including:

- **Citation Validity:** Whether references are genuine and their bibliographic information is accurate.
- **Claim Support:** Whether cited studies actually support the generated scientific claims.
- **Domain Accuracy:** Whether the response correctly distinguishes mental health concepts, causal relationships, and study populations.

This verification stage aims to reduce citation hallucinations, evidence mismatches, and unsupported scientific conclusions.

### 2.3 Evidence-Grounded Explanations

The **Explanation Agent** converts research findings into clear and accessible explanations for non-specialist users.

It aims to preserve important scientific limitations and uncertainties while avoiding unnecessary technical jargon.

### 2.4 Safety Interrupt

MindBridge implements a **Safety Interrupt mechanism at the Python workflow level**.

When the Research Agent returns a `safety_interrupt` status, the pipeline stops subsequent Verification and Explanation Agent calls and prioritizes an appropriate safety response.

This mechanism is designed to handle selected high-risk situations, such as potential self-harm risk or urgent physical symptoms.

### 2.5 Evidence Consistency Validation

MindBridge includes an additional Python-based Evidence Validation module.

This module checks whether the final Explanation output is consistent with the Verification Agent's recorded evidence.

This provides an additional structural constraint but does not replace independent verification against external scientific sources.

### 2.6 Interactive User Interface

MindBridge provides a **Streamlit-based interface** supporting:

- Mental health research questions
- English and Chinese interaction
- Multi-agent research processing
- Presentation of research findings and scientific references

---

## 3. Multi-Agent Architecture

MindBridge uses three independently configured agents within the SciencePal Multi-Agent platform.

### Workflow

```text
                  User Query
                      |
                      v
               Research Agent
          Custom Skill + Europe PMC
                      |
               Safety Interrupt?
                 /          \
               Yes           No
                |             |
                v             v
          Safety Response  Verification Agent
                           Custom Skill
                                |
                                v
                          Explanation Agent
                                |
                                v
                       Evidence Validation
                                |
                                v
                          Final Response
```

### Agent Responsibilities

| Agent | Responsibilities | Configuration |
|---|---|---|
| Research Agent | Scientific literature retrieval and organization | Custom Prompt + Custom Skill + Europe PMC API |
| Verification Agent | Citation, claim, and evidence verification | Custom Prompt + Custom Skill |
| Explanation Agent | Accessible and evidence-grounded explanations | Custom Prompt |

### Workflow Orchestration

The Python pipeline controls the execution sequence of the three agents using the SciencePal SDK.

The workflow includes:

1. **Safety Interrupt:** Stops normal processing when the configured interruption condition is triggered.
2. **Evidence Validation:** Checks consistency between verified evidence and the final explanation.
3. **Structured Output Handling:** Processes agent responses for downstream validation and presentation.

---

## 4. Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Frontend | Streamlit |
| Multi-Agent Platform | SciencePal Multi-Agent |
| Agent Integration | SciencePal SDK |
| Scientific Literature Database | Europe PMC |
| Literature Retrieval | Europe PMC API |
| Custom Agent Capabilities | Custom Prompts and Skills |
| Workflow Orchestration | Python Pipeline |
| Safety Mechanism | Python Safety Interrupt |
| Evidence Consistency | Custom Python Validation |
| Experimental Analysis | Python, Pandas, Matplotlib, Jupyter Notebook |

---

## 5. Project Structure

```text
MindBridge/
├── .streamlit/
│   └── secrets.toml                  # Local credentials (not committed)
│
├── app.py
├── research_results.py
├── scoring.py                        # Not developed as part of this Hackathon project
├── requirements.txt
├── README.md
│
├── services/
│   ├── sciencepal_client.py
│   └── sciencepal_stream_compat.py
│
├── workflows/
│   ├── research_pipeline.py
│   └── evidence_validation.py
│
├── tests/
│   ├── test_evidence_validation.py
│   ├── test_research_pipeline.py
│   └── test_safety_interrupt.py
│
├── agents/
│   ├── research_agent_prompt.md
│   ├── verification_agent_prompt.md
│   └── explanation_agent_prompt.md
│
└── skills/
    ├── research_skill.zip
    └── verification_skill.zip
```

### Project Components

- **`app.py`**: Main Streamlit application.
- **`services/`**: SciencePal SDK integration and response handling.
- **`workflows/research_pipeline.py`**: Agent IDs, multi-agent orchestration, and Safety Interrupt handling.
- **`workflows/evidence_validation.py`**: Evidence consistency validation.
- **`tests/`**: Automated tests for evidence validation, research pipeline execution, and safety interruption.
- **`agents/`**: Custom Agent Prompt files.
- **`skills/`**: Exported Custom Skill packages.

The `agents/` and `skills/` directories contain supplementary SciencePal resources and should be included when these resources are published.

The `.streamlit/secrets.toml` file is created locally and must never be committed to GitHub.

---

## 6. Installation & Setup

### 6.1 Prerequisites

Before running MindBridge, ensure you have:

- Python installed
- Access to the SciencePal Multi-Agent platform
- A valid SciencePal API Key
- Access to the configured Research, Verification, and Explanation Agents

### 6.2 Clone the Repository

Clone the GitHub repository:

```bash
git clone https://github.com/jme199/MindBridge.git
cd MindBridge
```

### 6.3 Install Dependencies

Install the required Python packages:

```bash
python -m pip install -r requirements.txt
```

### 6.4 Configure Streamlit Secrets

MindBridge uses Streamlit Secrets to manage sensitive credentials.

**Step 1 — Create the `.streamlit` directory**

In the project root directory, create a folder named `.streamlit`.

**Step 2 — Create `secrets.toml`**

Inside `.streamlit`, create a file named `secrets.toml`.

You can create both using the terminal:

```bash
mkdir -p .streamlit
touch .streamlit/secrets.toml
```

The resulting directory structure should be:

```text
MindBridge/
└── .streamlit/
    └── secrets.toml
```

**Step 3 — Add your SciencePal API Key**

Open `.streamlit/secrets.toml` and add your SciencePal API credentials using the configuration keys expected by your local application.

Example template:

```toml
SCIENCEPAL_API_KEY = "your_sciencepal_api_key"
```

Replace the placeholder with your actual API Key.

**Important:** The example key name must match the configuration expected by your version of `services/sciencepal_client.py` or the application entry point.

Do not add your Agent IDs to this file unless you have explicitly modified the application to load them from Streamlit Secrets.

### 6.5 Configure Agent IDs

MindBridge stores its Agent IDs in:

```text
workflows/research_pipeline.py
```

Find the `AGENT_IDS` dictionary near the beginning of the file.

The configuration follows this structure:

```python
AGENT_IDS = {
    "research": "your_research_agent_id",
    "verification": "your_verification_agent_id",
    "explanation": "your_explanation_agent_id",
}
```

Replace the placeholder values with the IDs of your configured SciencePal Agents.

You can find these IDs in the SciencePal platform after creating or accessing the corresponding Agents.

The following configurations are required:

- `research`: Research Agent ID
- `verification`: Verification Agent ID
- `explanation`: Explanation Agent ID

**Note:** The Agent IDs must correspond to Agents that your SciencePal account has permission to access. The provided Custom Skills must also be configured in the corresponding SciencePal Agents.

### 6.6 Run the Application

Start MindBridge using:

```bash
streamlit run app.py
```

Open the local URL displayed in the terminal to access the MindBridge application.

Full end-to-end execution requires valid SciencePal credentials and access to the configured Agents and their Custom Skills.

### 6.7 Custom Agent Prompts & Skills

MindBridge includes three independently designed Agent Prompts and two Custom Skills.

**Agent Prompts**

The `agents/` directory contains the following resources:

```text
agents/
├── research_agent_prompt.md
├── verification_agent_prompt.md
└── explanation_agent_prompt.md
```

These files describe each Agent's responsibilities, instructions, and expected behavior.

**Custom Skills**

The `skills/` directory contains:

```text
skills/
├── research_skill.zip
└── verification_skill.zip
```

The Research Skill supports scientific literature retrieval, including integration with Europe PMC.

The Verification Skill supports specialized citation and scientific evidence verification.

To reproduce the complete system, users may need to import or configure these Skills within their own SciencePal environment.

The availability of Skill import features and Agent sharing depends on SciencePal platform permissions.

### 6.8 Security & Reproducibility

Sensitive credentials must not be committed to public repositories.

Ensure that `.gitignore` includes:

```gitignore
# Streamlit secrets
.streamlit/secrets.toml

# Environment variables
.env
.env.*
!.env.example

# Python cache
__pycache__/
*.pyc

# Virtual environments
.venv/
venv/
```

**Security Guidelines**

- Never upload real API keys or access tokens.
- Do not include sensitive credentials inside Prompt files or Skill ZIP packages.
- Review exported Agent configurations before publishing.
- Use credentials associated with your own SciencePal account.
- Verify that shared Agent IDs and Skills are accessible with the appropriate platform permissions.

The public repository provides the Python source code and supporting technical resources. Full reproducibility also depends on the availability and configuration of external SciencePal services.

---

## 7. Experimental Evaluation

MindBridge is evaluated through a small-scale comparative pilot study involving three systems.

### 7.1 Experimental Groups

| System | Description |
|---|---|
| LLM | Direct language model generation without external retrieval |
| LLM + RAG | Retrieval-augmented generation without a separate verification stage |
| MindBridge | Multi-agent retrieval, verification, and explanation workflow |

### 7.2 Experimental Design

The experiment includes:

- **6 predefined test questions**
- **3 experimental systems**
- **18 experimental runs**
- **4 evidence quality and domain accuracy questions (Q1–Q4)**
- **2 high-risk safety scenarios (S1–S2)**

The evidence-related questions assess conceptual distinctions, causal interpretation, population generalizability, and citation reliability.

The safety scenarios evaluate responses to potential self-harm risk and urgent physical symptoms.

### 7.3 Evaluation Metrics

Nine metrics are evaluated across five dimensions.

| Dimension | Metrics |
|---|---|
| Evidence Reliability | Citation Validity, Claim Support |
| Domain Accuracy | Domain Accuracy |
| Safety | Weighted Safety Score, Unsafe Medical Advice Rate |
| User Experience | Readability Score, Empathy Score |
| System Reliability | Task Completion Rate, Execution Time |

The Weighted Safety Score uses a descriptive scoring scheme:

- Pass = 1.0
- Partial = 0.5
- Fail = 0.0

Readability and Empathy are evaluated using five-point rating scales.

### 7.4 Experimental Results

**Status: Dataset refinement and final analysis in progress.**

The final results will include:

- Citation validity and claim support comparisons
- Domain accuracy analysis
- Safety evaluation
- Readability and empathy comparisons
- Task completion and execution time
- Overall performance summary and visualizations

Results will be added after the final dataset has been verified.

The study is exploratory and does not establish statistical superiority or clinical effectiveness.

---

## 8. Limitations

MindBridge is an experimental research prototype with several limitations:

- Evidence verification still relies partly on LLM-based semantic judgments.
- The Python evidence validation mechanism checks consistency rather than independently establishing the factual correctness of all claims.
- Scientific literature retrieval depends on external database availability and coverage.
- The multi-agent workflow may introduce additional execution time.
- Safety testing currently covers a limited number of predefined scenarios.
- The small experimental dataset limits generalizability.
- The independent contribution of each Agent has not yet been isolated through ablation studies.

---

## 9. Future Work

Planned improvements include:

- Strengthening automated citation verification and claim-evidence matching
- Expanding evaluation datasets across additional mental health topics
- Conducting repeated testing and ablation studies
- Improving safety interruption coverage and robustness
- Optimizing multi-agent execution efficiency
- Evaluating readability and practical usefulness through user feedback

---

## 10. Responsible Use

**MindBridge is an educational and research prototype. It is not a medical device or a clinically validated mental health service.**

The system is not intended to:

- Diagnose mental health conditions
- Prescribe medication
- Provide individualized medical treatment
- Replace licensed healthcare or mental health professionals

AI-generated research information may contain errors or incomplete evidence and should not be used as the sole basis for healthcare decisions.

Users experiencing immediate danger or a medical emergency should seek appropriate professional or emergency assistance.

---

## 11. Project Contributions

The independently developed components of MindBridge include:

- Custom Multi-Agent role design and configuration
- Custom Agent Prompts
- Research and Verification Custom Skills
- Integration of scientific literature retrieval through Europe PMC
- Python-based multi-agent workflow orchestration
- Safety Interrupt implementation
- Evidence consistency validation
- Streamlit application interface
- Comparative experimental evaluation framework

The underlying multi-agent platform and model integration services are provided by SciencePal.

MindBridge's main contribution is the design and evaluation of a structured workflow that applies explicit evidence constraints and safety mechanisms to mental health research information generation.

---

**MindBridge — Bridging Mental Health Research and Trustworthy AI through Evidence Verification.**

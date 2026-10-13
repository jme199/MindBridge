# scoring.py
# MindBridge - GAD-7 Scoring Module


def calculate_gad7(answers):
    """
    Validate seven GAD-7 responses and calculate the total score.

    Parameters
    ----------
    answers : list
        Seven integer responses, each between 0 and 3.

    Returns
    -------
    dict
        Total score and non-diagnostic symptom category.
    """

    if not isinstance(answers, (list, tuple)):
        raise ValueError("Answers must be a list or tuple.")

    if len(answers) != 7:
        raise ValueError("Exactly seven answers are required.")

    for answer in answers:
        if type(answer) is not int:
            raise ValueError("Each answer must be an integer.")

        if not 0 <= answer <= 3:
            raise ValueError("Each answer must be between 0 and 3.")

    total = sum(answers)

    if 0 <= total <= 4:
        severity = "Minimal anxiety symptoms"
    elif 5 <= total <= 9:
        severity = "Mild anxiety symptoms"
    elif 10 <= total <= 14:
        severity = "Moderate anxiety symptoms"
    else:
        severity = "Severe anxiety symptoms"

    return {
        "answers": list(answers),
        "total_score": total,
        "severity": severity,
    }
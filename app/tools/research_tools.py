USER_SKILLS = {
    "python",
    "fastapi",
    "docker",
    "automation",
    "rag",
    "llm",
    "apis",
}


def get_sample_opportunities() -> list[dict]:
    return [
        {
            "title": "Python Automation Developer",
            "skills": ["Python", "Automation", "APIs"],
            "budget": "$150",
        },
        {
            "title": "FastAPI Backend Developer",
            "skills": ["Python", "FastAPI", "Docker"],
            "budget": "$250",
        },
        {
            "title": "AI RAG Developer",
            "skills": ["Python", "RAG", "LLM", "FastAPI"],
            "budget": "$300",
        },
    ]


def calculate_fit_score(opportunity: dict) -> int:
    required_skills = {
        skill.lower()
        for skill in opportunity.get("skills", [])
    }

    if not required_skills:
        return 0

    matched_skills = required_skills & USER_SKILLS

    return round(
        len(matched_skills) / len(required_skills) * 100
    )

def parse_budget(budget: str) -> int:
    cleaned = budget.replace("$", "").replace(",", "").strip()

    try:
        return int(cleaned)
    except ValueError:
        return 0


def calculate_payment_score(opportunity: dict) -> int:
    budget = parse_budget(opportunity.get("budget", "0"))

    if budget >= 300:
        return 100

    if budget >= 200:
        return 80

    if budget >= 100:
        return 60

    return 30


def make_decision(fit_score: int, payment_score: int) -> str:
    total_score = round(
        (fit_score * 0.7)
        + (payment_score * 0.3)
    )

    if total_score >= 80:
        return "APPLY"

    if total_score >= 60:
        return "MAYBE"

    return "SKIP"
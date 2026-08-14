from app.state import RouteType


def route_task(task: str) -> RouteType:
    text = task.lower()

    research_keywords = [
        "research",
        "find",
        "search",
        "investigate",
        "opportunity",
        "freelance",
    ]

    email_keywords = [
        "email",
        "reply",
        "message",
        "proposal",
        "send",
    ]

    calendar_keywords = [
        "calendar",
        "meeting",
        "schedule",
        "appointment",
        "remind",
    ]

    if any(keyword in text for keyword in research_keywords):
        return "research"

    if any(keyword in text for keyword in email_keywords):
        return "email"

    if any(keyword in text for keyword in calendar_keywords):
        return "calendar"

    return "unknown"
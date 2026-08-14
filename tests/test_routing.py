from app.graph import route_task


def test_routes_research_task():
    result = route_task(
        "Find freelance Python automation opportunities"
    )

    assert result == "research"


def test_routes_email_task():
    result = route_task(
        "Write an email proposal to the client"
    )

    assert result == "email"


def test_routes_calendar_task():
    result = route_task(
        "Schedule a meeting with the client"
    )

    assert result == "calendar"


def test_unknown_task():
    result = route_task(
        "Make me a cup of tea"
    )

    assert result == "unknown"
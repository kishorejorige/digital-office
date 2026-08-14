from app.tools.research_tools import (
    calculate_fit_score,
    calculate_payment_score,
    get_sample_opportunities,
    make_decision,
)


def run_research_agent(task: str) -> dict:
    opportunities = get_sample_opportunities()

    scored_opportunities = []

    for opportunity in opportunities:
        scored = opportunity.copy()

        fit_score = calculate_fit_score(opportunity)
        payment_score = calculate_payment_score(opportunity)
        decision = make_decision(
            fit_score,
            payment_score,
        )

        scored["fit_score"] = fit_score
        scored["payment_score"] = payment_score
        scored["decision"] = decision

        scored_opportunities.append(scored)

    scored_opportunities.sort(
        key=lambda item: (
            item["decision"] == "APPLY",
            item["fit_score"],
            item["payment_score"],
        ),
        reverse=True,
    )

    return {
        "agent": "research",
        "task": task,
        "status": "completed",
        "count": len(scored_opportunities),
        "opportunities": scored_opportunities,
    }
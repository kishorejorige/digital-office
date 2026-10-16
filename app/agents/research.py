from sqlalchemy.orm import Session

from app.models import Lead
from app.tools.research_tools import (
    calculate_fit_score,
    calculate_payment_score,
    get_sample_opportunities,
    make_decision,
)


def run_research_agent(
    task: str,
    db: Session | None = None,
) -> dict:
    opportunities = get_sample_opportunities()

    scored_opportunities = []
    saved_leads = 0

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

        if db is not None and decision == "APPLY":
            opportunity_url = opportunity.get("url")

            existing_query = db.query(Lead).filter(
                Lead.source == "Research Agent",
            )

            if opportunity_url:
                existing_lead = (
                    existing_query
                    .filter(Lead.url == opportunity_url)
                    .first()
                )
            else:
                existing_lead = (
                    existing_query
                    .filter(
                        Lead.url.is_(None),
                        Lead.title == opportunity["title"],
                    )
                    .first()
                )

            if existing_lead is None:
                lead = Lead(
                    source="Research Agent",
                    title=opportunity["title"],
                    url=opportunity_url,
                    budget=opportunity.get("budget"),
                    fit_score=fit_score,
                    payment_score=payment_score,
                    decision=decision,
                )

                db.add(lead)
                saved_leads += 1

    if db is not None:
        db.commit()

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
        "saved_leads": saved_leads,
        "opportunities": scored_opportunities,
    }

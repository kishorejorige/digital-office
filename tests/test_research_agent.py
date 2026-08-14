from app.agents.research import run_research_agent


def test_research_agent():
    result = run_research_agent(
        "Find freelance Python automation opportunities"
    )

    assert result["agent"] == "research"
    assert result["status"] == "completed"
    assert result["count"] == 3
    assert len(result["opportunities"]) == 3

def test_research_agent_scores_opportunities():
    result = run_research_agent(
        "Find freelance Python automation opportunities"
    )

    for opportunity in result["opportunities"]:
        assert "fit_score" in opportunity
        assert 0 <= opportunity["fit_score"] <= 100
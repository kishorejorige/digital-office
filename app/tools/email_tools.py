def build_proposal_draft(
    title: str,
    description: str | None,
) -> str:
    project_details = (
        description
        or "the project requirements you shared"
    )

    return (
        f"Hello,\n\n"
        f"I'm interested in your {title} project. "
        f"I have experience with Python, FastAPI, automation, "
        f"Docker, AI agents, and RAG-based applications.\n\n"
        f"Based on your requirement — {project_details} — "
        f"I'd be happy to discuss the simplest way to build "
        f"a reliable solution.\n\n"
        f"Regards,\n"
        f"Kishore"
    )
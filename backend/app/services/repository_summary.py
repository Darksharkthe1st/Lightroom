"""Template repository summary — replace with richer analysis later."""

from app.models.schemas import Repository, RepositorySummary


def build_template_summary(repo: Repository) -> RepositorySummary:
    lang = repo.language or "Unknown"
    desc = repo.description or "No description available."

    return RepositorySummary(
        full_name=repo.full_name,
        title=f"{repo.name} — Repository Overview",
        summary=(
            f"This is a template summary for **{repo.full_name}**. "
            f"{desc} "
            f"Primary language: {lang}. "
            f"Run analysis to generate resume bullets from your commits."
        ),
        highlights=[
            f"Last updated: {repo.updated_at or 'unknown'}",
            f"Visibility: {'private' if repo.private else 'public'}",
            f"Default branch: {repo.default_branch}",
        ],
        tech_stack=[lang] if repo.language else [],
        status="template",
    )

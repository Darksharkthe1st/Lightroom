from pathlib import Path

from app.services.analysis.artifact_loader import load_bullets, load_repo_analysis


DATA = Path(__file__).resolve().parents[1] / "data"
OWNER = "Darksharkthe1st"
REPO = "CodeRunner"


def test_load_coderunner_analysis():
    analysis = load_repo_analysis(DATA, OWNER, REPO)
    assert analysis.scout_complete
    assert analysis.status in ("analyzed", "scouted")
    assert analysis.rabbit_holes_planned >= 1


def test_load_coderunner_bullets():
    bullets = load_bullets(DATA, OWNER, REPO)
    assert len(bullets) >= 2
    assert all(b.source_repo == f"{OWNER}/{REPO}" for b in bullets)
    assert bullets[0].signal_id == "docker_execution_queue"

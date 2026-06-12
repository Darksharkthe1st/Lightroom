import os
from pathlib import Path

from app.config import settings
from app.services.analysis.artifact_loader import load_bullets, load_repo_analysis


def test_data_path_is_absolute_under_backend():
    assert settings.data_path.is_absolute()
    assert settings.data_path.name == "data"
    assert settings.data_path.parent.name == "backend"


def test_coderunner_bullets_survive_cwd_change():
    original = os.getcwd()
    try:
        os.chdir(Path(__file__).resolve().parents[2])  # repo root
        bullets = load_bullets(settings.data_path, "Darksharkthe1st", "CodeRunner")
        assert len(bullets) >= 2
        analysis = load_repo_analysis(settings.data_path, "Darksharkthe1st", "CodeRunner")
        assert analysis.status == "analyzed"
        assert analysis.scout_complete
    finally:
        os.chdir(original)

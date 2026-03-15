from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_readme_quick_start_uses_local_virtualenv_bootstrap():
    readme = (ROOT / "README.md").read_text()

    assert "python3 -m venv .venv" in readme
    assert ". .venv/bin/activate" in readme
    assert "python -m pip install --upgrade pip" in readme
    assert "python -m pip install -r requirements.txt" in readme
    assert "python -m pytest" in readme


def test_docker_compose_healthcheck_uses_python_not_curl():
    compose = (ROOT / "docker-compose.yml").read_text()

    assert "healthcheck:" in compose
    assert '"CMD", "python"' in compose
    assert "curl" not in compose
    assert "urllib.request.urlopen" in compose
    assert "http://localhost:8000/api/status" in compose


def test_ci_workflow_installs_dependencies_and_runs_pytest():
    workflow_path = ROOT / ".github" / "workflows" / "ci.yml"
    workflow = workflow_path.read_text()

    assert "actions/checkout" in workflow
    assert "actions/setup-python" in workflow
    assert "requirements.txt" in workflow
    assert "python -m pip install --upgrade pip" in workflow
    assert "python -m pip install -r requirements.txt" in workflow
    assert "python -m pytest" in workflow

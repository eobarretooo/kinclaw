from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_readme_quick_start_uses_local_virtualenv_bootstrap():
    readme = (ROOT / "README.md").read_text()

    assert "python3 -m venv .venv" in readme
    assert ". .venv/bin/activate" in readme
    assert "python -m pip install --upgrade pip" in readme
    assert "python -m pip install -r requirements.txt" in readme
    assert "python -m pytest" in readme
    assert "no chat channel configured by default" in readme
    assert "ANTHROPIC_API_KEY" in readme


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
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert "actions/checkout" in workflow
    assert "actions/setup-python" in workflow
    assert "requirements.txt" in workflow
    assert "python -m pip install --upgrade pip" in workflow
    assert "python -m pip install -r requirements.txt" in workflow
    assert "python -m pytest" in workflow
    docker_python = dockerfile.splitlines()[0].split(":", 1)[1].split("-", 1)[0]
    assert f'python-version: "{docker_python}"' in workflow


def test_env_example_defaults_to_no_active_chat_channels():
    env_example = (ROOT / ".env.example").read_text()
    env_lines = dict(
        line.split("=", 1)
        for line in env_example.splitlines()
        if line and not line.startswith("#") and "=" in line
    )

    assert env_lines["ACTIVE_CHANNELS"] == ""
    assert "Leave empty for local bootstrap without chat integrations" in env_example


def test_dockerfile_keeps_existing_python_runtime_and_reproducible_pip_install():
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert "FROM python:3.11-slim" in dockerfile
    assert "python -m pip install --upgrade pip" in dockerfile
    assert "python -m pip install --no-cache-dir -r requirements.txt" in dockerfile

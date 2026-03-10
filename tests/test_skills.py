import pytest
from kinclaw.skills.base import BaseSkill
from kinclaw.skills.registry import SkillRegistry


class EchoSkill(BaseSkill):
    name = "echo"
    description = "Echoes input back"

    async def execute(self, message: str = "") -> dict:
        return {"echo": message}

    async def validate(self, **kwargs) -> bool:
        return "message" in kwargs


@pytest.mark.asyncio
async def test_skill_execute():
    skill = EchoSkill()
    result = await skill.execute(message="hello")
    assert result["echo"] == "hello"


def test_registry_register_and_get():
    reg = SkillRegistry()
    reg.register(EchoSkill())
    skill = reg.get("echo")
    assert skill is not None
    assert skill.name == "echo"


def test_registry_list():
    reg = SkillRegistry()
    reg.register(EchoSkill())
    names = reg.list_names()
    assert "echo" in names


@pytest.mark.asyncio
async def test_registry_execute():
    reg = SkillRegistry()
    reg.register(EchoSkill())
    result = await reg.execute("echo", message="world")
    assert result["echo"] == "world"


@pytest.mark.asyncio
async def test_registry_raises_for_unknown_skill():
    reg = SkillRegistry()
    with pytest.raises(ValueError, match="Unknown skill"):
        await reg.execute("nonexistent")


from kinclaw.skills.builtin.file_manager import FileManagerSkill
from kinclaw.skills.builtin.code_analyzer import CodeAnalyzerSkill
from kinclaw.skills.builtin.code_executor import CodeExecutorSkill
from kinclaw.skills.loader import load_builtin_skills
import tempfile, os


@pytest.mark.asyncio
async def test_file_manager_write_and_read():
    skill = FileManagerSkill()
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "test.txt")
        result = await skill.execute(action="write", path=path, content="hello kinclaw")
        assert result["written"] is True

        result = await skill.execute(action="read", path=path)
        assert result["content"] == "hello kinclaw"


@pytest.mark.asyncio
async def test_code_analyzer_on_test_file():
    skill = CodeAnalyzerSkill()
    result = await skill.execute(path="kinclaw")
    assert result["files"] > 0
    assert result["lines"] > 0


@pytest.mark.asyncio
async def test_code_executor_runs_python():
    skill = CodeExecutorSkill()
    result = await skill.execute(code="print('kinclaw')", timeout=10)
    assert result["success"] is True
    assert "kinclaw" in result["stdout"]


def test_load_builtin_skills():
    reg = SkillRegistry()
    load_builtin_skills(reg)
    names = reg.list_names()
    assert "file_manager" in names
    assert "code_analyzer" in names
    assert "git_manager" in names
    assert "web_search" in names

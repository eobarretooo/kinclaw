"""Validation helpers for approved proposal execution."""

from __future__ import annotations

import asyncio
import importlib.util
import shutil
import sys
from pathlib import Path

from kinclaw.core.types import Proposal


class ProposalValidator:
    def __init__(self, tool_root: Path | None = None) -> None:
        self._tool_root = tool_root or Path(__file__).resolve().parents[2]

    async def validate(self, workspace_path: str, proposal: Proposal) -> dict:
        commands = self._build_commands()
        if not commands:
            return {
                "success": False,
                "returncode": None,
                "stdout": "",
                "stderr": "Missing validation tool: pytest",
                "commands": [],
            }

        for command in commands:
            result = await self._run(command, cwd=workspace_path)
            if not result["success"]:
                result["commands"] = [" ".join(cmd) for cmd in commands]
                return result

        return {"success": True, "commands": [" ".join(cmd) for cmd in commands]}

    def _build_commands(self) -> list[list[str]]:
        commands: list[list[str]] = []

        pytest_command = self._resolve_pytest_command()
        if pytest_command is None:
            return []
        commands.append(pytest_command)

        ruff_command = self._resolve_ruff_command()
        if ruff_command is not None:
            commands.append(ruff_command)

        return commands

    def _resolve_pytest_command(self) -> list[str] | None:
        local_pytest = self._tool_root / ".venv/bin/pytest"
        if local_pytest.exists():
            return [str(local_pytest)]

        global_pytest = shutil.which("pytest")
        if global_pytest:
            return [global_pytest]

        if importlib.util.find_spec("pytest") is not None:
            return [sys.executable, "-m", "pytest"]

        return None

    def _resolve_ruff_command(self) -> list[str] | None:
        local_ruff = self._tool_root / ".venv/bin/ruff"
        if local_ruff.exists():
            return [str(local_ruff), "check", "."]

        global_ruff = shutil.which("ruff")
        if global_ruff:
            return [global_ruff, "check", "."]

        return None

    async def _run(self, command: list[str], cwd: str) -> dict:
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
        except OSError as exc:
            return {
                "success": False,
                "returncode": None,
                "stdout": "",
                "stderr": str(exc),
            }
        stdout, stderr = await proc.communicate()
        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout.decode(errors="replace").strip(),
            "stderr": stderr.decode(errors="replace").strip()
            or stdout.decode(errors="replace").strip(),
        }

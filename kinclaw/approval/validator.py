"""Validation helpers for approved proposal execution."""

from __future__ import annotations

import asyncio
from pathlib import Path

from kinclaw.core.types import Proposal


class ProposalValidator:
    def __init__(self, tool_root: Path | None = None) -> None:
        self._tool_root = tool_root or Path(__file__).resolve().parents[2]

    async def validate(self, workspace_path: str, proposal: Proposal) -> dict:
        commands: list[list[str]] = [[str(self._tool_root / ".venv/bin/pytest")]]
        ruff_path = self._tool_root / ".venv/bin/ruff"
        if ruff_path.exists():
            commands.append([str(ruff_path), "check", "."])

        for command in commands:
            result = await self._run(command, cwd=workspace_path)
            if not result["success"]:
                result["commands"] = [" ".join(cmd) for cmd in commands]
                return result

        return {"success": True, "commands": [" ".join(cmd) for cmd in commands]}

    async def _run(self, command: list[str], cwd: str) -> dict:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await proc.communicate()
        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout.decode(errors="replace").strip(),
            "stderr": stderr.decode(errors="replace").strip()
            or stdout.decode(errors="replace").strip(),
        }

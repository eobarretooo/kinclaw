"""Executes Python code in a subprocess sandbox."""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from kinclaw.skills.base import BaseSkill
from kinclaw.logger import logger


class CodeExecutorSkill(BaseSkill):
    name = "code_executor"
    description = "Execute Python code in a sandboxed subprocess."

    async def execute(self, code: str = "", timeout: int = 30) -> dict:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            tmp_path = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "returncode": proc.returncode,
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "success": proc.returncode == 0,
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"returncode": -1, "stdout": "", "stderr": "Timeout exceeded", "success": False}
        finally:
            Path(tmp_path).unlink(missing_ok=True)

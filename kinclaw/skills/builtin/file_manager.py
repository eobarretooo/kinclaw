"""File read/write/list skill."""
from __future__ import annotations

import aiofiles
from pathlib import Path
from kinclaw.skills.base import BaseSkill


class FileManagerSkill(BaseSkill):
    name = "file_manager"
    description = "Read or write files on the local filesystem."

    async def execute(self, action: str = "read", path: str = "", content: str = "") -> dict:
        p = Path(path)
        if action == "read":
            if not p.exists():
                return {"error": f"File not found: {path}"}
            async with aiofiles.open(p, "r", encoding="utf-8", errors="replace") as f:
                text = await f.read()
            return {"content": text, "lines": text.count("\n") + 1}
        elif action == "write":
            p.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(p, "w", encoding="utf-8") as f:
                await f.write(content)
            return {"written": True, "path": str(p)}
        elif action == "list":
            if not p.is_dir():
                return {"error": "Not a directory"}
            files = [str(f.relative_to(p)) for f in p.rglob("*.py")]
            return {"files": files}
        return {"error": f"Unknown action: {action}"}

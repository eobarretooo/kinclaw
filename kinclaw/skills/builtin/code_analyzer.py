"""Analyzes Python code metrics."""
from __future__ import annotations

import ast
from pathlib import Path

from kinclaw.skills.base import BaseSkill


class CodeAnalyzerSkill(BaseSkill):
    name = "code_analyzer"
    description = "Analyze Python code: count lines, functions, complexity."

    async def execute(self, path: str = ".") -> dict:
        p = Path(path)
        py_files = list(p.rglob("*.py")) if p.is_dir() else [p]

        total_lines = total_funcs = total_classes = 0
        errors: list[str] = []

        for f in py_files:
            try:
                src = f.read_text(encoding="utf-8", errors="ignore")
                total_lines += src.count("\n") + 1
                tree = ast.parse(src)
                total_funcs += sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
                total_classes += sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
            except SyntaxError as e:
                errors.append(f"{f}: {e}")

        return {
            "files": len(py_files),
            "lines": total_lines,
            "functions": total_funcs,
            "classes": total_classes,
            "errors": errors,
        }

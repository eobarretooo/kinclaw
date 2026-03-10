"""Analyzes KinClaw's own codebase for metrics and improvement opportunities."""
from __future__ import annotations

import ast
from pathlib import Path

from kinclaw.logger import logger


class SelfAnalyzer:
    def __init__(self, base_path: Path = Path(".")) -> None:
        self._base = base_path

    async def analyze(self) -> dict:
        """Return metrics dict for the kinclaw/ package."""
        pkg = self._base / "kinclaw"
        py_files = list(pkg.rglob("*.py")) if pkg.exists() else []

        total_lines = total_funcs = total_classes = 0
        parse_errors = 0

        for f in py_files:
            try:
                src = f.read_text(encoding="utf-8", errors="ignore")
                total_lines += src.count("\n") + 1
                tree = ast.parse(src)
                total_funcs += sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
                total_classes += sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
            except SyntaxError:
                parse_errors += 1

        logger.info("SelfAnalyzer: {} files, {} lines, {} functions", len(py_files), total_lines, total_funcs)
        return {
            "metrics": {
                "files": len(py_files),
                "lines": total_lines,
                "functions": total_funcs,
                "classes": total_classes,
                "parse_errors": parse_errors,
            }
        }

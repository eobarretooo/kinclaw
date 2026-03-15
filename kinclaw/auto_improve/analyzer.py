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
        py_files = self._collect_code_files()
        test_files = self._collect_test_files()

        total_lines = total_funcs = total_classes = 0
        async_functions = documented_nodes = documentable_nodes = 0
        parse_errors = 0
        largest_files: list[dict] = []

        for f in py_files:
            try:
                src = f.read_text(encoding="utf-8", errors="ignore")
                line_count = src.count("\n") + 1
                total_lines += line_count
                tree = ast.parse(src)
                functions = [
                    n
                    for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                total_funcs += len(functions)
                async_functions += sum(
                    1 for n in functions if isinstance(n, ast.AsyncFunctionDef)
                )
                total_classes += len(classes)

                nodes = [tree, *functions, *classes]
                documentable_nodes += len(nodes)
                documented_nodes += sum(1 for n in nodes if ast.get_docstring(n))
                largest_files.append(
                    {
                        "path": str(f.relative_to(self._base)),
                        "lines": line_count,
                    }
                )
            except SyntaxError:
                parse_errors += 1

        largest_files.sort(key=lambda item: item["lines"], reverse=True)
        docstring_coverage_pct = (
            round((documented_nodes / documentable_nodes) * 100, 1)
            if documentable_nodes
            else 0.0
        )
        test_file_ratio = round(len(test_files) / len(py_files), 3) if py_files else 0.0
        async_function_ratio = (
            round(async_functions / total_funcs, 3) if total_funcs else 0.0
        )

        logger.info(
            "SelfAnalyzer: {} files, {} lines, {} functions",
            len(py_files),
            total_lines,
            total_funcs,
        )
        return {
            "metrics": {
                "files": len(py_files),
                "lines": total_lines,
                "functions": total_funcs,
                "classes": total_classes,
                "async_functions": async_functions,
                "async_function_ratio": async_function_ratio,
                "docstring_coverage_pct": docstring_coverage_pct,
                "test_files": len(test_files),
                "test_file_ratio": test_file_ratio,
                "non_test_files": len(
                    [path for path in py_files if not self._is_test_file(path)]
                ),
                "largest_files": largest_files[:3],
                "parse_errors": parse_errors,
            }
        }

    def _collect_code_files(self) -> list[Path]:
        preferred_pkg = self._base / "kinclaw"
        if preferred_pkg.exists():
            return list(preferred_pkg.rglob("*.py"))

        return [
            path
            for path in self._base.rglob("*.py")
            if not self._is_test_file(path) and not self._is_ignored_path(path)
        ]

    def _collect_test_files(self) -> list[Path]:
        tests_dir = self._base / "tests"
        test_files = list(tests_dir.rglob("test_*.py")) if tests_dir.exists() else []
        pkg_dir = self._base / "kinclaw"
        if pkg_dir.exists():
            test_files.extend(
                path for path in pkg_dir.rglob("*.py") if self._is_test_file(path)
            )
        else:
            test_files.extend(
                path
                for path in self._base.rglob("*.py")
                if self._is_test_file(path) and not self._is_ignored_path(path)
            )
        return test_files

    @staticmethod
    def _is_test_file(path: Path) -> bool:
        return any(part == "tests" for part in path.parts) or path.name.startswith(
            "test_"
        )

    @staticmethod
    def _is_ignored_path(path: Path) -> bool:
        ignored_parts = {".venv", ".git", "__pycache__", ".pytest_cache"}
        return any(part in ignored_parts or part.startswith(".") for part in path.parts)

"""Safety checks: forbidden paths, dangerous operations."""
from __future__ import annotations

FORBIDDEN_PATH_PREFIXES = [
    "kinclaw/guardrails/",
    "kinclaw/approval/",
    ".env",
    ".git/",
]


class SafetyChecker:
    """Verifies that proposed changes don't touch protected paths."""

    def is_safe_path(self, path: str) -> bool:
        normalized = path.replace("\\", "/").lstrip("/")
        return not any(normalized.startswith(p) for p in FORBIDDEN_PATH_PREFIXES)

    def is_safe_content(self, content: str) -> bool:
        """Heuristic checks for dangerous code patterns."""
        danger_patterns = [
            "os.system(",
            'subprocess.call("rm',
            "shutil.rmtree(",
            "__import__('os').system",
        ]
        return not any(p in content for p in danger_patterns)

    def validate_proposal_changes(self, code_changes: dict[str, str]) -> list[str]:
        """Return list of violations, empty means safe."""
        violations = []
        for path, content in code_changes.items():
            if not self.is_safe_path(path):
                violations.append(f"Forbidden path: {path}")
            if not self.is_safe_content(content):
                violations.append(f"Dangerous content in: {path}")
        return violations

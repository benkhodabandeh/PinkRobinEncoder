"""Static hygiene: compile check + unused-import sweep (ruff stand-in).

CI runs ruff, but this test guarantees the same two properties locally
without extra tooling: every module compiles, and no module carries an
unused import (the most common ruff F401 failure in this codebase's
history — e.g. a removed `re.fullmatch` leaving `import re` behind).
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

# `from __future__` and TYPE_CHECKING-only names are used implicitly.
IGNORED = {"annotations", "TYPE_CHECKING", "App"}


def _imports_and_uses(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported[(alias.asname or alias.name).split(".")[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                if alias.name != "*":
                    imported[alias.asname or alias.name] = node.lineno
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            inner = node
            while isinstance(inner, ast.Attribute):
                inner = inner.value
            if isinstance(inner, ast.Name):
                used.add(inner.id)
    return imported, used


def test_every_module_compiles():
    for path in sorted(SRC.glob("*.py")):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_no_unused_imports():
    offenders = []
    for path in sorted(SRC.glob("*.py")):
        if path.name == "__init__.py":
            continue
        imported, used = _imports_and_uses(path)
        for name, lineno in imported.items():
            if name not in used and name not in IGNORED:
                offenders.append(f"{path.name}:{lineno}: unused import {name!r}")
    assert not offenders, "Unused imports (would fail ruff F401):\n" + "\n".join(offenders)

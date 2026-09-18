from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], required: bool = True) -> int:
    print("> " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT)
    if required and proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return proc.returncode


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


if __name__ == "__main__":
    run([sys.executable, "-m", "compileall", "-q", "src"], required=True)

    if has_module("ruff"):
        run([sys.executable, "-m", "ruff", "check", "src", "scripts"], required=False)
    else:
        print("ruff not installed; skipping lint")

    if has_module("bandit"):
        run([sys.executable, "-m", "bandit", "-q", "-r", "src"], required=False)
    else:
        print("bandit not installed; skipping security lint")

    tests_dir = ROOT / "tests"
    if tests_dir.exists():
        # pyproject addopts require pytest-cov; degrade gracefully where it
        # is not installed (e.g. minimal local envs) instead of erroring.
        pytest_cmd = [sys.executable, "-m", "pytest", "-q"]
        if not has_module("pytest_cov"):
            print("pytest-cov not installed; running without coverage flags")
            pytest_cmd += ["-o", "addopts="]
        run(pytest_cmd, required=True)
    else:
        print("tests/ not found; pytest skipped")

    print("Developer checks completed.")

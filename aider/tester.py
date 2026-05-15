import os
import subprocess
from dataclasses import dataclass
from typing import Optional

from .scanner import scan_project


@dataclass
class TestResult:
    passed: int = 0
    failed: int = 0
    output: str = ""
    command_used: str = ""
    error: Optional[str] = None


def _run_test(cmd: str, project_root: str, timeout: int = 120) -> tuple[str, int]:
    try:
        r = subprocess.run(
            cmd.split(),
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (r.stdout + "\n" + r.stderr).strip()
        return output, r.returncode
    except subprocess.TimeoutExpired:
        return "command timed out", -1
    except FileNotFoundError:
        return "command not found", -1


def _parse_pytest_output(output: str) -> tuple[int, int]:
    """Parse pytest summary line like '24 passed, 0 failed'."""
    import re
    passed = 0
    failed = 0
    for line in output.split("\n"):
        m = re.search(r"(\d+)\s+passed", line)
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+)\s+failed", line)
        if m:
            failed = int(m.group(1))
    return passed, failed


def _detect_test_command(project_root: str, project_type: str) -> Optional[str]:
    test_cmds = {
        "python": ["python -m pytest", "pytest", "python -m unittest discover"],
        "rust": ["cargo test"],
        "node": ["npm test"],
        "go": ["go test ./..."],
        "make": ["make test"],
    }
    candidates = test_cmds.get(project_type, [])
    for cmd in candidates:
        base = cmd.split()[0]
        if base.startswith("python") or base.startswith("pytest"):
            # Check if pytest is installed
            r = subprocess.run(["which", "pytest"], capture_output=True, text=True)
            if r.returncode == 0:
                return cmd
            continue
        r = subprocess.run(["which", base.split()[0]], capture_output=True, text=True)
        if r.returncode == 0:
            return cmd
    return None


def find_and_run_tests(project_root: str, specific_cmd: Optional[str] = None) -> TestResult:
    result = TestResult()

    _, project_type = scan_project(project_root)

    if specific_cmd:
        # Try the suggested command first; fall back to auto-detect if it fails
        result.command_used = specific_cmd
        output, exit_code = _run_test(result.command_used, project_root)
        if exit_code != 0 and exit_code != -1:
            result.command_used = ""
    else:
        result.command_used = ""

    if not result.command_used:
        detected = _detect_test_command(project_root, project_type)
        if detected is None:
            result.error = "no test command found"
            return result
        result.command_used = detected
        output, exit_code = _run_test(result.command_used, project_root)

    result.output = output

    if exit_code == -1:
        result.error = output
        return result

    if result.command_used.startswith("python -m pytest") or result.command_used == "pytest":
        result.passed, result.failed = _parse_pytest_output(output)
    elif result.command_used == "cargo test":
        result.passed = 0 if exit_code != 0 else 1
        result.failed = 1 if exit_code != 0 else 0
    else:
        result.passed = 0 if exit_code != 0 else 1
        result.failed = 1 if exit_code != 0 else 0

    return result

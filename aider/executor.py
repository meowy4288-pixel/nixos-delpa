import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExecResult:
    success: bool = False
    applied_patches: list[str] = field(default_factory=list)
    command_output: str = ""
    command_exit: int = -1
    error: Optional[str] = None


def _run(cmd: list[str], cwd: str, timeout: int = 60) -> tuple[str, str, int]:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        return "", "command timed out", -1
    except FileNotFoundError:
        return "", "command not found", -1


def _git_stash(project_root: str, task_id: str) -> Optional[str]:
    """Stash current changes. Returns stash ref or None."""
    # Check if it's a git repo
    stdout, stderr, code = _run(["git", "rev-parse", "--git-dir"], project_root)
    if code != 0:
        # Init git repo
        _run(["git", "init"], project_root)
        _run(["git", "add", "-A"], project_root)
        _run(["git", "commit", "--allow-empty", "-m", "initial"], project_root)

    stdout, stderr, code = _run(["git", "stash", "push", "-m", f"aider-pre-{task_id}"], project_root)
    if code == 0 and "No local changes" not in stdout:
        return f"stash@{{0}}"
    return None


def _git_rollback(project_root: str):
    _run(["git", "checkout", "--", "."], project_root)


def _normalize_diff(diff: str) -> str:
    """Ensure diff has git-style 'a/' and 'b/' prefixes."""
    lines = diff.split("\n")
    out = []
    for line in lines:
        if line.startswith("--- ") and not line.startswith("--- a/"):
            line = "--- a/" + line[4:]
        if line.startswith("+++ ") and not line.startswith("+++ b/"):
            line = "+++ b/" + line[4:]
        out.append(line)
    return "\n".join(out)


def _git_apply(project_root: str, diff: str) -> Optional[str]:
    """Apply a unified diff. Returns None on success, error string on failure."""
    diff = _normalize_diff(diff)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False) as f:
        f.write(diff)
        diff_path = f.name
    try:
        stdout, stderr, code = _run(["git", "apply", "--unidiff-zero", diff_path], project_root)
        if code != 0:
            return stderr.strip() or "git apply failed"
        return None
    finally:
        os.unlink(diff_path)


def _git_pop_stash(project_root: str):
    _run(["git", "stash", "pop"], project_root)


def execute_patches(
    project_root: str,
    patches: list[tuple[str, str, bool]],  # (file_path, diff_or_content, is_replace)
    commands: list[str],
    task_id: str,
) -> ExecResult:
    result = ExecResult()

    # Git checkpoint: save pre-existing dirty state
    stash_ref = _git_stash(project_root, task_id)

    # Apply patches
    for file_path, diff_or_content, is_replace in patches:
        if is_replace:
            # Full file replacement
            abs_path = os.path.join(project_root, file_path)
            try:
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, "w") as f:
                    f.write(diff_or_content)
            except OSError as e:
                result.error = f"failed to write {file_path}: {e}"
                if stash_ref is not None:
                    _git_rollback(project_root)
                    _git_pop_stash(project_root)
                return result
        else:
            # Apply unified diff
            err = _git_apply(project_root, diff_or_content)
            if err:
                result.error = f"failed to apply patch for {file_path}: {err}"
                if stash_ref is not None:
                    _git_rollback(project_root)
                    _git_pop_stash(project_root)
                return result
        result.applied_patches.append(file_path)

    # Run commands
    for cmd in commands:
        stdout, stderr, code = _run(cmd.split(), project_root)
        result.command_output = (stdout + stderr).strip()
        result.command_exit = code
        if code != 0:
            result.error = f"command failed: {cmd}\n{result.command_output}"
            if stash_ref is not None:
                _git_rollback(project_root)
                _git_pop_stash(project_root)
            return result

    # Restore user's pre-existing changes on top of our patches
    if stash_ref is not None:
        _git_pop_stash(project_root)

    result.success = True
    return result

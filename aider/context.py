import os
from typing import Optional

from .scanner import FileInfo, scan_project, _extract_symbols

MAX_PRIMARY_TOKENS = 6000
MAX_SECONDARY_FILES = 30


def _token_estimate(text: str) -> int:
    return len(text) // 4


def _read_file(path: str) -> Optional[str]:
    try:
        with open(path, errors="replace") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def _score_file(finfo: FileInfo, goal: str, project_type: str) -> float:
    score = 0.0
    goal_lower = goal.lower()
    path_lower = finfo.path.lower()

    if goal_lower in path_lower:
        score += 100

    if project_type == "python" and finfo.extension == ".py":
        score += 5
    elif project_type == "rust" and finfo.extension == ".rs":
        score += 5
    elif project_type == "node" and finfo.extension in (".js", ".ts"):
        score += 5
    elif project_type == "go" and finfo.extension == ".go":
        score += 5

    goal_words = set(goal_lower.split())
    for sym in finfo.symbols:
        if sym.lower() in goal_lower or any(w in sym.lower() for w in goal_words):
            score += 30
            break

    path_parts = set(path_lower.replace(os.sep, "/").split("/"))
    for part in path_parts:
        if part in goal_words:
            score += 15

    if finfo.size < 5000:
        score += 3
    elif finfo.size < 20000:
        score += 1

    return score


def build_context(
    project_path: str,
    goal: str,
    previous_error: Optional[str] = None,
    requested_files: Optional[list[str]] = None,
) -> tuple[list[tuple[str, str]], list[tuple[str, list[str]]], int, list[FileInfo]]:
    """Build context with full file contents for direct LLM use."""
    files, project_type = scan_project(project_path)

    if not files:
        return [], [], 0, files

    for finfo in files:
        abs_path = os.path.join(project_path, finfo.path)
        finfo.symbols = _extract_symbols(abs_path)

    for finfo in files:
        finfo._score = _score_file(finfo, goal, project_type)
    files.sort(key=lambda f: f._score, reverse=True)

    primary: list[tuple[str, str]] = []
    secondary: list[tuple[str, list[str]]] = []
    seen = set()
    token_budget = MAX_PRIMARY_TOKENS

    if previous_error:
        token_budget = int(token_budget * 0.7)

    if requested_files:
        for rf in requested_files:
            for finfo in files:
                if finfo.path == rf or finfo.path.endswith("/" + rf):
                    abs_path = os.path.join(project_path, finfo.path)
                    content = _read_file(abs_path)
                    if content:
                        primary.append((finfo.path, content))
                        seen.add(finfo.path)
                        token_budget -= _token_estimate(content)
                    break

    for finfo in files:
        if finfo.path in seen:
            continue
        if finfo.size == 0:
            continue
        if token_budget <= 0:
            break
        abs_path = os.path.join(project_path, finfo.path)
        content = _read_file(abs_path)
        if content is None:
            continue
        estimated = _token_estimate(content)
        if estimated > token_budget:
            continue
        primary.append((finfo.path, content))
        seen.add(finfo.path)
        token_budget -= estimated

    count = 0
    for finfo in files:
        if count >= MAX_SECONDARY_FILES:
            break
        if finfo.path in seen:
            continue
        secondary.append((finfo.path, finfo.symbols))
        seen.add(finfo.path)
        count += 1

    total_tokens = sum(_token_estimate(c) for _, c in primary)
    total_tokens += sum(len(s) for _, s in secondary)

    return primary, secondary, total_tokens, files


def build_private_context(
    project_path: str,
    goal: str,
) -> tuple[list[tuple[str, list[str]]], str, int]:
    """Build a sanitized context — paths and symbols ONLY. No source code.

    Used in private mode: this summary is sent to the remote API.
    The remote API never sees file contents, only structure.
    Returns: (files_with_symbols, project_structure_summary, total_files)
    """
    files, project_type = scan_project(project_path)

    if not files:
        return [], "", 0

    # Extract symbols only (no file contents)
    for finfo in files:
        abs_path = os.path.join(project_path, finfo.path)
        finfo.symbols = _extract_symbols(abs_path)

    # Build a structural summary
    lines = [f"Project type: {project_type}", f"Total files: {len(files)}", ""]

    file_list = []
    for finfo in sorted(files, key=lambda f: f.path):
        if finfo.symbols:
            sym_str = ", ".join(finfo.symbols[:15])
            lines.append(f"  {finfo.path}  [{finfo.extension}]  symbols: {sym_str}")
        else:
            lines.append(f"  {finfo.path}  [{finfo.extension}]")
        file_list.append((finfo.path, finfo.symbols))

    summary = "\n".join(lines)
    return file_list, summary, len(files)

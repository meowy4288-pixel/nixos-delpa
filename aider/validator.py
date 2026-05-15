import os
import re
from dataclasses import dataclass, field
from typing import Optional

BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
                     ".woff", ".woff2", ".ttf", ".eot",
                     ".pyc", ".so", ".dll", ".dylib",
                     ".db", ".sqlite", ".sqlite3",
                     ".lock", ".sum"}

DESTRUCTIVE_PATTERNS = re.compile(
    r"\b(rm\s+-[rf]|dd\s+|mkfs\.|chmod\s+777|sudo\s+rm|>?\s*/dev/\w+|:\(\)\s*\{|:\(\)\s*\|"
    r"|chown\s+-R|chattr\s+|swapoff|shutdown|reboot|halt|poweroff"
    r"|wget\s+.*\|\s*(?:bash|sh)|curl\s+.*\|\s*(?:bash|sh))"
)

SAFE_NEW_FILE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go",
    ".c", ".h", ".cpp", ".hpp", ".java", ".kt", ".swift",
    ".rb", ".php", ".pl", ".pm",
    ".html", ".css", ".scss", ".less",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".md", ".rst", ".txt",
    ".sh", ".bash", ".zsh", ".fish",
    ".sql", ".graphql",
    ".xml", ".csv",
    ".env.example", ".gitignore", ".dockerignore",
    ".editorconfig", ".eslintrc", ".prettierrc",
    ".module", ".def",
}


@dataclass
class ValidationResult:
    approved: bool = False
    approved_commands: list[str] = field(default_factory=list)
    approved_patches: list[tuple[str, str, bool]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _is_safe_path(file_path: str, project_root: str) -> tuple[bool, Optional[str]]:
    if os.path.isabs(file_path):
        return False, "absolute path not allowed"
    normalized = os.path.normpath(file_path)
    if normalized.startswith("..") or "/.." in normalized:
        return False, "parent traversal not allowed"
    abspath = os.path.abspath(os.path.join(project_root, normalized))
    proj_abs = os.path.abspath(project_root)
    if not (abspath.startswith(proj_abs + os.sep) or abspath == proj_abs):
        return False, "path escapes project root"
    return True, None


def _is_binary_extension(file_path: str) -> bool:
    _, ext = os.path.splitext(file_path)
    return ext.lower() in BINARY_EXTENSIONS


def _is_code_extension(file_path: str) -> bool:
    _, ext = os.path.splitext(file_path)
    return ext.lower() in SAFE_NEW_FILE_EXTENSIONS


def _is_valid_diff(diff: str) -> tuple[bool, Optional[str]]:
    if not diff.strip():
        return False, "empty diff"
    lines = diff.split("\n")
    has_header = False
    has_hunk = False
    for line in lines:
        if line.startswith("--- ") or line.startswith("+++ "):
            has_header = True
        elif line.startswith("@@"):
            has_hunk = True
    if not has_header:
        return False, "diff missing '---'/'+++' headers"
    if not has_hunk:
        return False, "diff missing '@@' hunk headers"
    return True, None


def _is_safe_command(cmd: str, allowlist: list[str]) -> bool:
    cmd_stripped = cmd.strip()
    for allowed in allowlist:
        if cmd_stripped == allowed or cmd_stripped.startswith(allowed + " "):
            return True
    return False


def validate_response(
    data: dict,
    project_root: str,
    command_allowlist: list[str],
    max_diff_lines: int = 500,
) -> ValidationResult:
    result = ValidationResult()

    resp_type = data.get("type")

    if resp_type in ("plan", "request_info"):
        result.approved = True
        return result

    if resp_type == "patch":
        patches = data.get("patches", [])
        for p in patches:
            file_path = p.get("file", "")

            # Validate path safety
            safe, path_err = _is_safe_path(file_path, project_root)
            if not safe:
                result.errors.append(f"unsafe path '{file_path}': {path_err}")
                continue

            # Check for binary extensions (warn, don't block)
            if _is_binary_extension(file_path):
                result.warnings.append(f"binary file extension: {file_path}")
                continue

            # File existence check — allow new files with code extensions
            full_path = os.path.join(project_root, file_path)
            file_exists = os.path.exists(full_path)
            if not file_exists:
                if not _is_code_extension(file_path):
                    result.errors.append(
                        f"new file '{file_path}' has unrecognized extension "
                        f"(add to SAFE_NEW_FILE_EXTENSIONS or create manually)"
                    )
                    continue

            content = p.get("content")
            diff = p.get("diff")
            is_replace = bool(content and not diff)

            if is_replace:
                if len(content) > 100000:
                    result.errors.append(f"content for {file_path} too large: {len(content)} chars")
                    continue
                if DESTRUCTIVE_PATTERNS.search(content):
                    result.errors.append(f"destructive pattern detected in content for {file_path}")
                    continue
                result.approved_patches.append((file_path, content, True))
            else:
                if not diff:
                    result.errors.append(f"no diff or content for {file_path}")
                    continue
                if not file_exists:
                    result.errors.append(f"cannot diff non-existent file '{file_path}'; use content instead")
                    continue
                valid, err_msg = _is_valid_diff(diff)
                if not valid:
                    result.errors.append(f"invalid diff for {file_path}: {err_msg}")
                    continue
                diff_lines = diff.count("\n")
                if diff_lines > max_diff_lines:
                    result.errors.append(f"diff for {file_path} too large: {diff_lines} lines (max {max_diff_lines})")
                    continue
                if DESTRUCTIVE_PATTERNS.search(diff):
                    result.errors.append(f"destructive pattern detected in diff for {file_path}")
                    continue
                result.approved_patches.append((file_path, diff, False))

        # Validate optional test command
        test_cmd = data.get("test_command")
        if test_cmd:
            if _is_safe_command(test_cmd, command_allowlist):
                result.approved_commands.append(test_cmd)
            else:
                result.errors.append(f"command not in allowlist: {test_cmd}")

        if not result.errors:
            if result.approved_patches or result.approved_commands:
                result.approved = True
            else:
                result.errors.append("no patches or commands to execute")

    return result

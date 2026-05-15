import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


IGNORE_PATTERNS = {
    ".git", "__pycache__", "node_modules", "target", "build", "dist",
    ".venv", "venv", ".eggs", "*.pyc", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "*.so", ".aiderignore",
    # System / cache directories
    ".npm", ".cache", ".local", ".nvm", ".bun",
    ".rustup", ".cargo", ".go",
    "snap", "go", "Library", "Applications",
    ".mozilla", ".config", ".vscode", ".idea",
    ".Trash", ".thumbnails",
    # Container / VM
    ".docker", "vagrant",
}


@dataclass
class FileInfo:
    path: str  # relative to project root
    size: int
    extension: str
    symbols: list[str] = field(default_factory=list)
    content: Optional[str] = None

    @property
    def abs_path(self) -> str:
        return self.path

    def __lt__(self, other):
        return self.path < other.path


SYMBOL_PATTERNS: dict[str, list[str]] = {
    ".py": [
        r"^\s*(?:async\s+)?def\s+(\w+)\s*\(",
        r"^\s*(?:async\s+)?class\s+(\w+)",
    ],
    ".rs": [
        r"^\s*(?:pub\s+)?fn\s+(\w+)",
        r"^\s*(?:pub\s+)?(?:struct|enum|trait|impl)\s+(\w+)",
    ],
    ".js": [
        r"^\s*(?:export\s+(?:default\s+)?)?(?:function|class)\s+(\w+)",
        r"^\s*(?:export\s+)?const\s+(\w+)\s*=",
    ],
    ".ts": [
        r"^\s*(?:export\s+(?:default\s+)?)?(?:function|class|interface|type)\s+(\w+)",
        r"^\s*(?:export\s+)?const\s+(\w+)\s*=",
    ],
    ".go": [
        r"^\s*func\s+(\w+)",
        r"^\s*type\s+(\w+)\s+(?:struct|interface)",
    ],
    ".c": [r"^\s*(?:static\s+)?(?:int|void|char|size_t|bool|struct)\s+(\w+)\s*\("],
    ".h": [r"^\s*(?:extern\s+)?(?:int|void|char|size_t|bool|struct)\s+(\w+)\s*\("],
    ".java": [
        r"^\s*(?:public|private|protected|static)?\s*(?:class|interface|enum)\s+(\w+)",
        r"^\s*(?:public|private|protected)?\s+\w+\s+(\w+)\s*\(",
    ],
    ".toml": [],
    ".json": [],
    ".md": [],
    ".yaml": [],
    ".yml": [],
    ".txt": [],
}


def _should_ignore(name: str) -> bool:
    if name in IGNORE_PATTERNS:
        return True
    for pat in IGNORE_PATTERNS:
        if pat.startswith("*") and name.endswith(pat[1:]):
            return True
    return False


def _load_aiderignore(project_path: str) -> set[str]:
    ignore_path = os.path.join(project_path, ".aiderignore")
    if not os.path.exists(ignore_path):
        return set()
    patterns = set()
    with open(ignore_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.add(line)
    return patterns


def _extract_symbols(path: str) -> list[str]:
    _, ext = os.path.splitext(path)
    patterns = SYMBOL_PATTERNS.get(ext, [])
    if not patterns:
        return []
    try:
        with open(path, errors="replace") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return []
    symbols = []
    for pat in patterns:
        symbols.extend(m.group(1) for m in re.finditer(pat, content, re.MULTILINE))
    return symbols


def _detect_project_type(project_path: str) -> str:
    if os.path.exists(os.path.join(project_path, "pyproject.toml")):
        return "python"
    if os.path.exists(os.path.join(project_path, "Cargo.toml")):
        return "rust"
    if os.path.exists(os.path.join(project_path, "package.json")):
        return "node"
    if os.path.exists(os.path.join(project_path, "go.mod")):
        return "go"
    if os.path.exists(os.path.join(project_path, "Makefile")):
        return "make"
    if os.path.exists(os.path.join(project_path, "CMakeLists.txt")):
        return "cmake"
    # Fallback: check for source files
    for f in os.listdir(project_path):
        if f.endswith(".py"):
            return "python"
        if f.endswith(".rs"):
            return "rust"
        if f.endswith((".js", ".ts", ".jsx", ".tsx")):
            return "node"
        if f.endswith(".go"):
            return "go"
        if f.endswith((".c", ".h", ".cpp", ".hpp")):
            return "make"
    return "unknown"


def scan_project(project_path: str) -> tuple[list[FileInfo], str]:
    project_type = _detect_project_type(project_path)
    ignore_patterns = _load_aiderignore(project_path)
    files = []

    for root, dirs, names in os.walk(project_path):
        dirs[:] = [d for d in dirs if not _should_ignore(d) and d not in ignore_patterns]
        for name in names:
            if _should_ignore(name) or name in ignore_patterns:
                continue
            full = os.path.join(root, name)
            rel = os.path.relpath(full, project_path)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            _, ext = os.path.splitext(name)
            files.append(FileInfo(path=rel, size=size, extension=ext))

    return files, project_type

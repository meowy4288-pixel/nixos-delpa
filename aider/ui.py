import sys
import shutil
import time
import threading
import re
from contextlib import contextmanager

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_ITALIC = "\033[3m"
_RED = "\033[91m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_BLUE = "\033[94m"
_MAGENTA = "\033[95m"
_CYAN = "\033[96m"
_WHITE = "\033[97m"

_TERM_WIDTH: int = 80

# Global output capture for web UI (thread-safe)
_output_callbacks: list[callable] = []
_output_lock = threading.Lock()
_original_stderr = sys.stderr


class _CaptureWriter:
    def write(self, text):
        _original_stderr.write(text)
        _original_stderr.flush()
        if text.strip():
            clean = re.sub(r"\033\[[0-9;]*m", "", text)
            with _output_lock:
                cbs = list(_output_callbacks)
            for cb in cbs:
                try:
                    cb(clean)
                except Exception:
                    pass

    def flush(self):
        _original_stderr.flush()


def add_output_callback(cb: callable):
    with _output_lock:
        if not _output_callbacks:
            sys.stderr = _CaptureWriter()
        _output_callbacks.append(cb)


def remove_output_callback(cb: callable):
    with _output_lock:
        _output_callbacks.remove(cb)
        if not _output_callbacks:
            sys.stderr = _original_stderr


def _init():
    global _TERM_WIDTH
    _TERM_WIDTH = min(shutil.get_terminal_size((80, 20)).columns, 100)


def _line(char: str = "─", color: str = _DIM, width: int | None = None) -> str:
    w = width or _TERM_WIDTH
    return color + char * w + _RESET


def title(text: str):
    pad = _TERM_WIDTH - len(text) - 2
    if pad < 2:
        pad = 2
    left = pad // 2
    right = pad - left
    print(f"\n{_line('━', _WHITE)}", file=sys.stderr)
    print(f" {_BOLD}{_WHITE}{' ' * left}{text}{' ' * right}{_RESET}", file=sys.stderr)
    print(f"{_line('━', _WHITE)}", file=sys.stderr)


def section(title: str):
    print(file=sys.stderr)
    print(f" {_BOLD}{_CYAN}▌ {title}{_RESET}", file=sys.stderr)
    print(f" {_DIM}▌{_line('─', _DIM, _TERM_WIDTH - 2)}{_RESET}", file=sys.stderr)


def status(msg: str):
    print(f" {_BLUE}◆{_RESET} {msg}", file=sys.stderr)


def ok(msg: str):
    print(f" {_GREEN}✓{_RESET} {msg}", file=sys.stderr)


def warn(msg: str):
    print(f" {_YELLOW}⚠{_RESET} {msg}", file=sys.stderr)


def err(msg: str):
    print(f" {_RED}✗{_RESET} {msg}", file=sys.stderr)


def detail(msg: str):
    print(f"   {_DIM}{msg}{_RESET}", file=sys.stderr)


def muted(msg: str):
    print(f"   {_DIM}{_ITALIC}{msg}{_RESET}", file=sys.stderr)


def sub_section(title: str):
    print(f"   {_CYAN}├─ {title}{_RESET}", file=sys.stderr)


def plan_step(i: int, total: int, desc: str, files: list[str] | None = None):
    print(f"   {_MAGENTA}{i + 1}/{total}{_RESET} {desc}", file=sys.stderr)
    if files:
        print(f"      {_DIM}files: {', '.join(files)}{_RESET}", file=sys.stderr)


def remote_call(model: str, tokens: int):
    print(f"\n {_BOLD}{_YELLOW}☁{_RESET} remote ({_BOLD}{model}{_RESET})", file=sys.stderr)
    detail(f"{tokens} prompt tokens  |  No source code sent")
    muted("Paths and symbols only")


def local_call(model: str, tokens: int):
    print(f"\n {_BOLD}{_GREEN}◉{_RESET} local ({_BOLD}{model}{_RESET})", file=sys.stderr)
    detail(f"{tokens} prompt tokens")


def patch_applied(file_path: str, added: int, removed: int):
    badge = f"{_GREEN}+{added}{_RESET}" if added else ""
    badge += f"{_RED}-{removed}{_RESET}" if removed else ""
    spacer = " " if badge else ""
    print(f"   {_DIM}~{_RESET} {file_path} {spacer}{badge}", file=sys.stderr)


def test_result(passed: int, failed: int):
    if failed == 0 and passed > 0:
        print(f"   {_BOLD}{_GREEN}{passed} passed{_RESET}", file=sys.stderr)
    elif failed == 0:
        print(f"   {_DIM}no tests run{_RESET}", file=sys.stderr)
    else:
        print(f"   {_BOLD}{_RED}{failed} failed{_RESET}, {passed} passed", file=sys.stderr)


def result_line(status_str: str, retries: int, duration: float):
    if status_str == "success":
        tag = f"{_GREEN}{_BOLD}✔ SUCCESS{_RESET}"
    else:
        tag = f"{_RED}{_BOLD}✘ FAILED{_RESET}"
    print(f" {tag}  ({retries} retries, {duration:.1f}s)", file=sys.stderr)
    print(f" {_line('═', _GREEN if status_str == 'success' else _RED)}", file=sys.stderr)


def config_check(severity: str, msg: str):
    if severity == "ok":
        icon = f"{_GREEN}✓{_RESET}"
    elif severity == "warn":
        icon = f"{_YELLOW}⚠{_RESET}"
    else:
        icon = f"{_RED}✗{_RESET}"
    print(f"   {icon}  {_DIM}{msg}{_RESET}", file=sys.stderr)


# ── Spinner ──

class Spinner:
    _FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, msg: str = ""):
        self._msg = msg
        self._running = False
        self._thread: threading.Thread | None = None

    def _spin(self):
        i = 0
        while self._running:
            frame = self._FRAMES[i % len(self._FRAMES)]
            sys.stderr.write(f"\r {_CYAN}{frame}{_RESET} {self._msg}")
            sys.stderr.flush()
            time.sleep(0.08)
            i += 1
        sys.stderr.write("\r" + " " * (_TERM_WIDTH) + "\r")
        sys.stderr.flush()

    def start(self, msg: str = ""):
        if msg:
            self._msg = msg
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
            self._thread = None


@contextmanager
def spinner(msg: str = ""):
    s = Spinner(msg)
    s.start()
    try:
        yield s
    finally:
        s.stop()


_init()

import json
import os
import tomllib
import urllib.request
import urllib.error
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

CONFIG_DIR = os.path.expanduser("~/.config/aider")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.toml")
COMMANDS_PATH = os.path.join(CONFIG_DIR, "commands.toml")
LOG_DIR = os.path.expanduser("~/.local/share/aider/logs")

DEFAULT_ALLOWLIST: list[str] = [
    "pytest", "cargo test", "npm test", "go test", "make test",
    "python -m pytest", "cargo build", "npm run build", "go build",
    "make build", "ruff", "ruff check", "black", "flake8", "mypy",
    "cargo fmt --check",
]


@dataclass
class Config:
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5-coder:1.5b"
    llm_api_key: str = "sk-no-key-required"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096
    llm_timeout: int = 300

    remote_base_url: str = ""
    remote_model: str = ""
    remote_api_key: str = ""
    remote_timeout: int = 60

    private_mode: bool = False

    max_retries: int = 5
    max_diff_lines: int = 500
    max_context_tokens: int = 6000

    command_allowlist: list[str] = field(default_factory=lambda: DEFAULT_ALLOWLIST.copy())

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        if not os.path.exists(CONFIG_PATH):
            return cfg
        with open(CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        for key, value in data.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        return cfg

    def validate(self) -> list[tuple[str, str]]:
        """Run preflight checks. Returns list of (severity, message) tuples.
        Severity is 'ok', 'warn', or 'error'."""
        checks: list[tuple[str, str]] = []

        # ── Local model ──
        if not self.llm_model:
            checks.append(("error", "llm_model is not set"))
        else:
            checks.append(self._check_ollama_available())
            checks.append(self._check_model_exists(self.llm_model))

        # ── Local base URL ──
        if not self.llm_base_url:
            checks.append(("error", "llm_base_url is not set"))
        elif "localhost" in self.llm_base_url or "127.0.0.1" in self.llm_base_url:
            checks.append(("ok", "local Ollama endpoint"))
        else:
            checks.append(("ok", f"remote endpoint: {self.llm_base_url}"))

        # ── Remote (private mode) ──
        if self.private_mode:
            if not self.remote_base_url:
                checks.append(("error", "private mode requires remote_base_url"))
            elif not self.remote_api_key:
                checks.append(("error", "private mode requires remote_api_key"))
            elif not self.remote_model:
                checks.append(("error", "private mode requires remote_model"))
            else:
                checks.append(("ok", f"remote planner: {self.remote_model}"))
                checks.append(self._check_remote_reachable())
        else:
            checks.append(("ok", "private mode off"))

        # ── Sanity checks ──
        if self.llm_temperature < 0 or self.llm_temperature > 2:
            checks.append(("warn", f"llm_temperature={self.llm_temperature} is unusual (0-2)"))
        if self.llm_timeout < 60:
            checks.append(("warn", f"llm_timeout={self.llm_timeout}s is very short for CPU inference; recommend ≥300"))
        if self.max_retries < 1:
            checks.append(("warn", "max_retries should be ≥1"))
        if self.max_context_tokens < 1024:
            checks.append(("warn", f"max_context_tokens={self.max_context_tokens} is very low"))

        return checks

    def _check_ollama_available(self) -> tuple[str, str]:
        base = self.llm_base_url.rstrip("/v1").rstrip("/")
        url = base + "/api/tags"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return ("ok", "Ollama reachable")
                return ("warn", f"Ollama returned status {resp.status}")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            return ("error", f"Ollama unreachable: {e}")

    def _check_model_exists(self, model: str) -> tuple[str, str]:
        base = self.llm_base_url.rstrip("/v1").rstrip("/")
        url = base + "/api/tags"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                if model in models:
                    return ("ok", f"model '{model}' found locally")
                for m in models:
                    if model.split(":")[0] == m.split(":")[0]:
                        return ("warn", f"model '{model}' not found; similar: {m}")
                return ("warn", f"model '{model}' not pulled yet. Run: ollama pull {model}")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
            return ("warn", "could not verify model (Ollama may be starting)")

    def _check_remote_reachable(self) -> tuple[str, str]:
        try:
            req = urllib.request.Request(self.remote_base_url.rstrip("/") + "/models")
            req.add_header("Authorization", f"Bearer {self.remote_api_key}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return ("ok", f"remote API reachable (HTTP {resp.status})")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return ("ok", "remote API reachable (auth required)")
            return ("warn", f"remote API returned {e.code}")
        except (urllib.error.URLError, OSError) as e:
            return ("warn", f"remote API unreachable: {e}")


def load_command_allowlist() -> list[str]:
    if not os.path.exists(COMMANDS_PATH):
        return DEFAULT_ALLOWLIST.copy()
    with open(COMMANDS_PATH, "rb") as f:
        data = tomllib.load(f)
    return data.get("allow", DEFAULT_ALLOWLIST.copy())


def ensure_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

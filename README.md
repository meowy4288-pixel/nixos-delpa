# aider — Local Coding Agent

**aider** is a privacy-first, task-driven coding agent that runs entirely on your machine. It scans a project, sends relevant context to a local LLM (Ollama), generates patches, validates them, applies them, and runs tests — all from a single CLI command or web UI.

No data ever leaves your computer (unless you enable optional private mode with a remote planner).

## Quick Start

```bash
# 1. Install Ollama if you haven't
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull a code model
ollama pull qwen2.5-coder:1.5b

# 3. Install aider
cd ~/local-agent
pip install -e .

# 4. Run
aider "add input validation to the login form"
```

## Usage

### CLI

```bash
# Basic task
aider "add a function to validate email addresses"

# Specify project (default: current directory)
aider --project ~/myapp "refactor user model"

# Read task from file
aider --task-file task.txt

# Dry run — show plan without making changes
aider --dry-run "migrate to new API"

# Private mode (remote plans, local executes, source code NEVER leaves)
aider --private "add authentication"
```

### Web UI

```bash
aider serve
# Opens http://127.0.0.1:8712 in your browser
```

Full-screen web interface with:
- Task input and project path
- Real-time output streaming via SSE
- Dry-run toggle
- Private mode toggle

## How It Works

```
  Scanner ──► Context Builder ──► LLM ──► Parser ──► Validator ──► Executor ──► Tester
     │              │               │          │            │            │         │
     └── finds      └── scores      └── local  └── extracts └── checks   └── applies└── runs
         relevant       & ranks         Ollama      JSON +      safety        patches     tests
         files          files           model       code        & paths
                                                    blocks
```

On failure at any step, the loop retries with the error message as context (up to `max_retries` times).

## Private Mode

```
  Remote API (planning)           Local Model (execution)
       │                                │
       │  file paths + symbol names     │
       │  (NO source code)              │
       ▼                                ▼
  ┌──────────────┐              ┌──────────────────┐
  │ "modify      │── steps ────►│  generate code   │
  │  auth.py:    │              │  validate        │
  │  login()"    │              │  apply           │
  └──────────────┘              │  test            │
                                └──────────────────┘
```

Enable in `~/.config/aider/config.toml`:
```toml
private_mode = true
remote_base_url = "https://api.openai.com/v1"
remote_model = "gpt-4o"
remote_api_key = "sk-..."
```

## Configuration

File: `~/.config/aider/config.toml`

```toml
# Local model (code generation)
llm_model = "qwen2.5-coder:1.5b"
llm_base_url = "http://127.0.0.1:11434/v1"
llm_timeout = 300

# Behavior
max_retries = 5
max_context_tokens = 6000

# Private mode (optional)
private_mode = false
remote_base_url = ""
remote_model = ""
remote_api_key = ""
```

## Files

```
~/local-agent/
├── aider/              # Python package
│   ├── __init__.py     # Package metadata
│   ├── __main__.py     # python3 -m aider entry point
│   ├── main.py         # CLI entry point
│   ├── serve.py        # Web UI server (stdlib only)
│   ├── config.py       # Config loading and validation
│   ├── task.py         # Task dataclass
│   ├── scanner.py      # File discovery and symbol extraction
│   ├── context.py      # Context building + private mode builder
│   ├── prompt.py       # LLM prompt construction
│   ├── llm.py          # LLM API caller (OpenAI-compatible)
│   ├── parser.py       # JSON + code block parser
│   ├── validator.py    # Patch/command safety validation
│   ├── executor.py     # Git-stash apply/rollback
│   ├── tester.py       # Auto-detect and run tests
│   ├── loop.py         # Main retry orchestrator
│   ├── hybrid.py       # Private mode planner
│   ├── logger.py       # Structured file logging
│   └── ui.py           # Terminal output + web capture
├── pyproject.toml       # Package build config
├── README.md            # This file
└── .gitignore
```

## Requirements

- **Python 3.10+** (tested on 3.14)
- **Ollama** with a code model (0.5b / 1.5b / 3b)
- **Linux** (Fedora, Ubuntu, Mint, etc.) — macOS should work, Windows untested
- **CPU only** — no GPU required, but GPU makes it 10-50x faster

## Performance Notes

On CPU with `qwen2.5-coder:1.5b`:
- Context evaluation: ~5ms per token (30s for 6000 tokens)
- Generation: ~200ms per token (3–5 tokens/sec)
- Typical task: 30–90 seconds per iteration

## Project Status

v1.0.0 — Core pipeline complete. Ready for daily use on small-to-medium codebases.
Future: GPU support, more model backends, plugin system, persistent sessions.

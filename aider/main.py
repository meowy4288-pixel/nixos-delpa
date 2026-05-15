import argparse
import os
import sys

from . import __version__, __app_name__
from .config import Config, ensure_dirs
from .task import Task
from .loop import run_task
from .ui import title, section, status, config_check, err as ui_err


DESCRIPTION = f"""
{__app_name__} v{__version__} — Task-first private coding agent.

Aider reads your project, sends relevant context to an LLM,
generates patches, validates them, applies them, and runs tests.

Private mode: remote API plans (no source code ever leaves),
local model executes the plan.

Commands:
  aider TASK              Run a task
  aider serve             Start web UI

Examples:
  aider "fix the bug in login.py"
  aider --dry-run "refactor the database layer"
  aider --private "add user authentication" --project ~/myapp
  aider --task-file task.txt --project .
  aider serve
"""


def run_goal(goal: str, project_path: str, private: bool = False, dry_run: bool = False) -> bool:
    """Shared entry point used by both CLI and web UI."""
    config = Config.load()
    if private:
        config.private_mode = True

    if config.private_mode:
        if not config.remote_base_url or not config.remote_model or not config.remote_api_key:
            ui_err("Private mode requires remote_base_url, remote_model, and remote_api_key in config")
            return False

    if not os.path.isdir(project_path):
        ui_err(f"Project path does not exist: {project_path}")
        return False

    title(f"{__app_name__} v{__version__}")

    section("Preflight")
    checks = config.validate()
    has_errors = False
    for severity, msg in checks:
        config_check(severity, msg)
        if severity == "error":
            has_errors = True
    if has_errors:
        ui_err("Preflight checks failed. Fix config and try again.")
        return False

    status(f"Goal: {goal[:80]}{'...' if len(goal) > 80 else ''}")
    status(f"Project: {project_path}")
    if config.private_mode:
        status(f"Model: local={config.llm_model}  remote={config.remote_model}")
    else:
        status(f"Model: {config.llm_model}")
    if dry_run:
        status("Dry run — no changes will be made")

    task = Task(goal=goal, project_path=project_path)
    return run_task(task, config=config, dry_run=dry_run)


def main():
    ensure_dirs()

    parser = argparse.ArgumentParser(
        prog=__app_name__,
        description=DESCRIPTION.strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("goal", nargs="*", help="Task description (e.g., 'add login form')")
    parser.add_argument("--project", "-p", default=os.getcwd(),
                        help="Project root directory (default: current dir)")
    parser.add_argument("--task-file", "-f",
                        help="Read task from file instead of command line")
    parser.add_argument("--private", action="store_true",
                        help="Enable private mode: remote plans, local executes. Source code NEVER leaves.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes")
    parser.add_argument("--version", "-v", action="version",
                        version=f"{__app_name__} {__version__}")

    args = parser.parse_args()

    # ── Serve subcommand ──
    if args.goal and args.goal[0] == "serve":
        from .serve import start_server
        start_server()
        return

    # ── Resolve goal ──
    if args.task_file:
        try:
            with open(args.task_file) as f:
                goal = f.read().strip()
        except OSError as e:
            ui_err(f"Cannot read task file: {e}")
            sys.exit(1)
    elif args.goal:
        goal = " ".join(args.goal)
    else:
        parser.print_help()
        sys.exit(1)

    # ── Resolve project path ──
    project_path = os.path.abspath(args.project)
    if not os.path.isdir(project_path):
        ui_err(f"Project path does not exist: {project_path}")
        sys.exit(1)

    success = run_goal(goal, project_path, args.private, args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

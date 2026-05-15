import time
from typing import Optional

from .task import Task
from .config import Config, load_command_allowlist
from .context import build_context
from .prompt import build_messages
from .llm import call_llm, count_tokens
from .parser import parse_response
from .validator import validate_response
from .executor import execute_patches
from .tester import find_and_run_tests
from .logger import Logger
from .hybrid import create_plan
from .ui import section, status, ok as ui_ok, warn, err as ui_err, detail, muted, sub_section
from .ui import patch_applied, test_result, result_line, local_call, spinner


def run_task(task: Task, config: Optional[Config] = None, dry_run: bool = False) -> bool:
    if config is None:
        config = Config.load()

    log = Logger(task.task_id)
    log.task(task.goal, task.project_path)

    command_allowlist = load_command_allowlist()
    start = time.time()
    retry_count = 0
    max_retries = config.max_retries
    previous_error: Optional[str] = None
    requested_files: Optional[list[str]] = None

    # ── Private mode: remote plans, local executes ──
    if config.private_mode and retry_count == 0:
        section(f"Task: {task.goal}")
        status("Private mode — remote API plans, local model executes")

        sub_tasks = create_plan(config, task)
        if sub_tasks is not None:
            ui_ok(f"Got {len(sub_tasks)} plan steps from remote planner")
            if dry_run:
                muted("Dry run — plans will not be executed")
                duration = time.time() - start
                result_line("success", retry_count, duration)
                log.result("success", retry_count, duration)
                log.close()
                return True

            all_ok = True
            for i, sub in enumerate(sub_tasks):
                sub_section(f"Step {i+1}: {sub.goal[:60]}")
                ok = run_task(sub, config, dry_run=dry_run)
                if not ok:
                    ui_err(f"Step {i+1} failed")
                    all_ok = False
                    break
            duration = time.time() - start
            result_line("success" if all_ok else "failed", retry_count, duration)
            if all_ok:
                log.result("success", retry_count, duration)
            else:
                log.result("failed", retry_count, duration)
            log.close()
            return all_ok
        else:
            warn("Plan creation failed, falling back to local-only mode")

    # ── Main retry loop ──
    while retry_count <= max_retries:
        section(f"Iteration {retry_count + 1}")

        # ── Build context ──
        primary, secondary, total_tokens, all_files = build_context(
            project_path=task.project_path,
            goal=task.goal,
            previous_error=previous_error,
            requested_files=requested_files,
        )
        requested_files = None
        log.retrieve(files=len(primary) + len(secondary), tokens=total_tokens)

        status(f"Context: {len(primary)} primary + {len(secondary)} secondary files, ~{total_tokens} tokens")

        if not primary and not secondary:
            ui_err("No files found in project")
            log.error("context", "no files found in project")
            log.close()
            return False

        # ── Build prompt & call LLM ──
        messages = build_messages(task.goal, primary, secondary, previous_error)
        prompt_tokens, _ = count_tokens(messages, config)

        local_call(config.llm_model, prompt_tokens)

        with spinner("Generating..."):
            raw = call_llm(messages, config)

        if raw is None:
            ui_err("LLM call failed after retries")
            log.error("llm", "LLM call failed after retries")
            log.close()
            return False

        output_tokens = len(raw) // 4
        log.llm_call(config.llm_model, prompt_tokens, output_tokens)
        detail(f"Response: {len(raw)} chars")

        # ── Parse ──
        parsed, parse_err = parse_response(raw)
        if parse_err:
            ui_err(f"Parse: {parse_err}")
            log.validate("fail", parse_err)
            previous_error = parse_err
            retry_count += 1
            continue

        resp_type = parsed["type"]
        log.validate("parsed", f"type={resp_type}")
        detail(f"Type: {resp_type}")

        # ── request_info ──
        if resp_type == "request_info":
            if not parsed.get("requested_files"):
                previous_error = "request_info returned empty file list"
                retry_count += 1
                continue
            if retry_count >= max_retries:
                ui_err("Max retries exceeded on request_info")
                break
            requested_files = parsed["requested_files"]
            previous_error = f"LLM requested additional files: {requested_files}"
            warn(f"Need more files: {requested_files}")
            retry_count += 1
            continue

        # ── plan ──
        if resp_type == "plan":
            steps = parsed.get("steps", [])
            log.validate("plan", f"{len(steps)} steps")

            if dry_run:
                ui_ok(f"Plan: {len(steps)} steps (dry run)")
                for i, step in enumerate(steps):
                    desc = step.get("description", f"step {i}")
                    files = step.get("files", [])
                    muted(f"  {i+1}. {desc}")
                    if files:
                        muted(f"     files: {', '.join(files)}")
                duration = time.time() - start
                result_line("success", retry_count, duration)
                log.result("success", retry_count, duration)
                log.close()
                return True

            status(f"Executing plan: {len(steps)} steps")
            all_ok = True
            for i, step in enumerate(steps):
                desc = step.get("description", f"step {i}")
                sub_section(f"Step {i+1}: {desc[:60]}")
                sub_task = Task(
                    goal=desc,
                    project_path=task.project_path,
                    task_id=f"{task.task_id}-s{i}",
                )
                ok = run_task(sub_task, config, dry_run=dry_run)
                if not ok:
                    ui_err(f"Step {i} failed: {desc}")
                    all_ok = False
                    break
            duration = time.time() - start
            result_line("success" if all_ok else "failed", retry_count, duration)
            if all_ok:
                log.result("success", retry_count, duration)
            else:
                log.result("failed", retry_count, duration)
            log.close()
            return all_ok

        # ── patch ──
        if resp_type == "patch":
            validation = validate_response(
                parsed,
                project_root=task.project_path,
                command_allowlist=command_allowlist,
                max_diff_lines=config.max_diff_lines,
            )

            # Show warnings
            for w in validation.warnings:
                warn(w)

            if not validation.approved:
                err_msg = "; ".join(validation.errors)
                ui_err(f"Validation: {err_msg}")
                log.validate("fail", err_msg)
                previous_error = err_msg
                retry_count += 1
                continue

            log.validate("pass", f"{len(validation.approved_patches)} patches")
            ui_ok(f"Validated: {len(validation.approved_patches)} patches")

            for file_path, diff_or_content, is_replace in validation.approved_patches:
                if not is_replace:
                    added = diff_or_content.count("\n+")
                    removed = diff_or_content.count("\n-")
                else:
                    lines = diff_or_content.count("\n") + 1
                    added = lines
                    removed = 0
                log.patch(file_path, added, removed)
                patch_applied(file_path, added, removed)

            if dry_run:
                muted("Dry run — patches not applied")
                if validation.approved_commands:
                    muted(f"Would run: {' | '.join(validation.approved_commands)}")
                duration = time.time() - start
                result_line("success", retry_count, duration)
                log.result("success", retry_count, duration)
                log.close()
                return True

            # ── Execute ──
            result = execute_patches(
                task.project_path,
                validation.approved_patches,
                validation.approved_commands,
                task.task_id,
            )

            if result.error:
                log.execute(result.command_output[:200] if result.command_output else "", result.command_exit)
                log.error("execution", result.error)
                ui_err(f"Execution: {result.error[:200]}")
                previous_error = result.error
                retry_count += 1
                continue

            for cmd in validation.approved_commands:
                log.execute(cmd, result.command_exit)
                detail(f"Command: {cmd} (exit={result.command_exit})")

            # ── Test ──
            test_cmd = parsed.get("test_command")
            test_result_obj = find_and_run_tests(task.project_path, test_cmd)
            log.test(test_result_obj.passed, test_result_obj.failed, test_result_obj.command_used)
            test_result(test_result_obj.passed, test_result_obj.failed)

            if test_result_obj.failed > 0:
                previous_error = (
                    f"Tests failed: {test_result_obj.failed} failed, {test_result_obj.passed} passed.\n"
                    f"{test_result_obj.output[:1000]}"
                )
                warn("Tests failed, retrying...")
                retry_count += 1
                continue

            duration = time.time() - start
            result_line("success", retry_count, duration)
            log.result("success", retry_count, duration)
            log.close()
            return True

    # ── Loop exhausted ──
    duration = time.time() - start
    result_line("failed", retry_count, duration)
    log.result("failed", retry_count, duration)
    log.close()
    return False

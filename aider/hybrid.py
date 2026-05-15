"""Hybrid planner: remote API plans (no source code), local model executes."""

import json
import time
import urllib.request
import urllib.error
from typing import Optional

from .config import Config
from .context import build_private_context
from .task import Task
from .ui import section, remote_call, detail, plan_step, status, warn, err as ui_err, spinner


_PRIVATE_SYSTEM_PROMPT = """\
You are a software architecture planner. Your role: analyze project structure and produce a step-by-step plan.

You NEVER see source code. You only see file paths and symbol names (function/class definitions).

## Input format
You receive a project structure summary listing:
- File paths (relative to project root)
- File extensions
- Defined symbols (function/class names) in each file

## Output
Respond with valid JSON ONLY:
```json
{
  "type": "plan",
  "reasoning": "Brief reasoning about what needs to change",
  "steps": [
    {
      "description": "What to do in this step (specific, actionable)",
      "files": ["relative/file/path.py"]
    }
  ]
}
```

## Rules
- Each step must list the specific files that need to change
- Steps are executed sequentially by a separate code-generation engine
- Be specific about what needs to change in each file (mention symbol names)
- Do NOT suggest new file creation unless absolutely necessary
- Keep the plan to 5 or fewer steps
- You only see file paths and symbols — reason about the structure only
"""


def _call_remote(messages: list[dict], config: Config) -> Optional[str]:
    """Call the remote API for planning with retries and backoff."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.remote_api_key}",
    }
    url = config.remote_base_url.rstrip("/") + "/chat/completions"

    last_error = None
    for attempt in range(3):
        payload = {
            "model": config.remote_model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 2048,
        }
        data = json.dumps(payload).encode()

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=config.remote_timeout) as resp:
                result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:200]
            last_error = f"HTTP {e.code}: {body}"
            if e.code in (429, 500, 502, 503):
                wait = 2 ** attempt
                warn(f"Remote API {e.code}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            break
        except (urllib.error.URLError, OSError) as e:
            last_error = str(e)
            if attempt < 2:
                wait = 2 ** attempt
                warn(f"Remote connection error, retrying in {wait}s...")
                time.sleep(wait)
                continue
            break
        except json.JSONDecodeError as e:
            last_error = f"invalid JSON response: {e}"
            break

    ui_err(f"Remote API failed after {attempt + 1} attempts: {last_error}")
    return None


def _parse_plan(raw: str) -> Optional[list[dict]]:
    """Extract steps from a plan response with format recovery."""
    cleaned = raw.strip()

    # Try ```json block
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1]
        if "```" in cleaned:
            cleaned = cleaned.split("```", 1)[0]
    # Try bare ``` block
    elif "```" in cleaned:
        parts = cleaned.split("```")
        if len(parts) >= 3:
            cleaned = parts[1]
            # Skip language identifier if present
            if cleaned.startswith("json\n"):
                cleaned = cleaned[5:]
        else:
            cleaned = parts[-1]

    cleaned = cleaned.strip()

    # Try parsing JSON
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: find outermost { }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                return None
        else:
            return None

    if not isinstance(data, dict):
        return None
    if data.get("type") != "plan":
        # Accept plan without type field if it has steps
        if "steps" not in data:
            return None

    steps = data.get("steps", [])
    if not isinstance(steps, list) or len(steps) == 0:
        return None

    # Validate each step
    valid = []
    for s in steps:
        if isinstance(s, dict) and "description" in s:
            valid.append(s)
    return valid if valid else None


def create_plan(config: Config, task: Task) -> Optional[list[Task]]:
    """Call remote API with sanitized context, return list of sub-tasks."""
    section("Hybrid Plan")

    file_list, summary, total_files = build_private_context(
        project_path=task.project_path,
        goal=task.goal,
    )

    if total_files == 0:
        ui_err("No files found in project")
        return None

    status(f"Scanned {total_files} files (symbols only, no source code)")

    user_prompt = f"""Task: {task.goal}

Project structure:
{summary}

Analyze this project structure and produce a plan. Remember: you only see file paths and symbols."""

    messages = [
        {"role": "system", "content": _PRIVATE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    prompt_tokens = len(user_prompt) // 4
    remote_call(config.remote_model, prompt_tokens)

    with spinner("Contacting remote planner..."):
        raw = _call_remote(messages, config)

    if raw is None:
        return None

    detail(f"Response: {len(raw)} chars")

    with spinner("Parsing plan..."):
        steps = _parse_plan(raw)

    if not steps:
        ui_err("Could not parse plan from remote response")
        detail(f"Raw response (first 300 chars): {raw[:300]}")
        return None

    status(f"Plan: {len(steps)} steps")

    sub_tasks = []
    for i, step in enumerate(steps):
        desc = step.get("description", f"Step {i+1}")
        files = step.get("files", [])
        plan_step(i, len(steps), desc, files)
        sub = Task(
            goal=desc,
            project_path=task.project_path,
            task_id=f"{task.task_id}-p{i}",
        )
        sub_tasks.append(sub)

    return sub_tasks

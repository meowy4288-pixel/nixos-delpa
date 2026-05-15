import json
import re
from typing import Any, Optional


def _extract_json_block(text: str) -> Optional[str]:
    """Extract JSON from the first ```json ... ``` block."""
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Fallback: try bare { ... }
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return m.group(0).strip()
    return None


def _extract_diff_blocks(text: str) -> list[str]:
    """Extract all diff blocks. Try ```diff first, then ``` as fallback."""
    blocks = re.findall(r"```diff\s*\n(.*?)\n```", text, re.DOTALL)
    if not blocks:
        all_blocks = re.findall(r"```(?:\w*)\s*\n(.*?)\n```", text, re.DOTALL)
        for b in all_blocks:
            if b.startswith("--- ") or b.startswith("+++ "):
                blocks.append(b)
    return blocks


def _extract_content_blocks(text: str) -> list[str]:
    """Extract code blocks that are NOT json or diff (these are file contents)."""
    all_blocks = re.findall(r"```(\w*)\s*\n(.*?)\n```", text, re.DOTALL)
    contents = []
    for lang, body in all_blocks:
        lang = lang.strip().lower()
        stripped = body.strip()
        if lang == "json" or stripped.startswith("{"):
            continue
        if lang == "diff" or stripped.startswith("--- "):
            continue
        contents.append(body)
    return contents


def _validate_patch_schema(data: dict) -> list[str]:
    errors = []
    patches = data.get("patches", [])
    if not isinstance(patches, list) or len(patches) == 0:
        errors.append("missing or empty 'patches' list")
        return errors
    for i, p in enumerate(patches):
        if not isinstance(p, dict):
            errors.append(f"patches[{i}]: not an object")
            continue
        if "file" not in p:
            errors.append(f"patches[{i}]: missing 'file'")
    if "test_command" in data and not isinstance(data["test_command"], str):
        errors.append("'test_command' must be a string")
    return errors


SCHEMAS = {
    "patch": {"type": "patch", "reasoning": str, "patches": list, "test_command": (str, type(None))},
    "plan": {"type": "plan", "reasoning": str, "steps": list},
    "request_info": {"type": "request_info", "reasoning": str, "requested_files": list},
}


def parse_response(raw: str) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Parse and validate LLM response. Returns (parsed_dict, error_string).

    Format for patch:
        ```json
        { "type": "patch", "patches": [{"file": "path"}], "test_command": "..." }
        ```
        ```diff
        --- a/file
        +++ b/file
        @@ ... @@
        ...
        ```
    """
    # Extract JSON metadata
    json_str = _extract_json_block(raw)
    if json_str is None:
        return None, "no JSON found in response"

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"

    if not isinstance(data, dict):
        return None, "response is not a JSON object"

    resp_type = data.get("type")
    if resp_type not in SCHEMAS:
        return None, f"unknown type '{resp_type}'; must be one of: {', '.join(SCHEMAS)}"

    if resp_type == "patch":
        errs = _validate_patch_schema(data)
        if errs:
            return data, "; ".join(errs)

        # Attach full file content blocks to patches
        patches = data.get("patches", [])
        contents = _extract_content_blocks(raw)

        if len(contents) == 0:
            # Fallback: try extracting diff blocks
            diffs = _extract_diff_blocks(raw)
            if len(diffs) > 0:
                for i, p in enumerate(patches):
                    if i < len(diffs):
                        p["diff"] = diffs[i]
                    else:
                        return data, f"no diff for patches[{i}]"
                if len(diffs) > len(patches):
                    for d in diffs[len(patches):]:
                        m = re.search(r"\+\+\+ b/(\S+)", d)
                        fname = m.group(1) if m else "unknown"
                        patches.append({"file": fname, "diff": d})
                return data, None
            else:
                return data, "no content or diff blocks found in response"

        if len(contents) > len(patches):
            for i in range(min(len(patches), len(contents))):
                patches[i]["content"] = contents[i]
            for c in contents[len(patches):]:
                patches.append({"file": "unknown", "content": c})
        else:
            for i, p in enumerate(patches):
                if i < len(contents):
                    p["content"] = contents[i]
                else:
                    return data, f"no content block for patches[{i}]"

    if resp_type == "plan":
        steps = data.get("steps", [])
        if not isinstance(steps, list) or len(steps) == 0:
            return data, "plan must have at least one step"
        for i, step in enumerate(steps):
            if not isinstance(step, dict) or "description" not in step:
                return data, f"steps[{i}]: missing 'description'"

    if resp_type == "request_info":
        files = data.get("requested_files", [])
        if not isinstance(files, list) or len(files) == 0:
            return data, "request_info must have non-empty 'requested_files' list"

    if "reasoning" not in data:
        data["reasoning"] = ""

    return data, None

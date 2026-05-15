import textwrap
from typing import Optional

SYSTEM_PROMPT = textwrap.dedent("""\
You are a precise coding assistant. Respond with valid JSON followed by code blocks.

## Responses

### plan — for multi-step tasks
```json
{"type": "plan", "reasoning": "...", "steps": [{"description": "...", "files": ["path"]}]}
```

### patch — for code changes
```json
{"type": "patch", "reasoning": "...", "patches": [{"file": "path"}], "test_command": ""}
```
Then for each file, output a code block with its COMPLETE new content:
```python
<entire new file content here>
```

### request_info — need more context
```json
{"type": "request_info", "reasoning": "...", "requested_files": ["path"]}
```

## Rules
- ALL file paths are relative to project root
- No destructive commands
- Output the complete file content in code blocks after the JSON
""")


def build_messages(
    goal: str,
    primary_files: list[tuple[str, str]],
    secondary_files: list[tuple[str, list[str]]],
    previous_error: Optional[str] = None,
) -> list[dict[str, str]]:
    user_parts = [f"Task: {goal}\n"]

    if primary_files:
        user_parts.append("Current files:")
        for path, content in primary_files:
            user_parts.append(f"\n### {path}\n```\n{content}\n```")

    if secondary_files:
        user_parts.append("\nOther files (symbols only):")
        for path, symbols in secondary_files:
            if symbols:
                user_parts.append(f"  {path}: {', '.join(symbols[:8])}")
            else:
                user_parts.append(f"  {path}")

    if previous_error:
        user_parts.append(f"\nPrevious error:\n{previous_error}")
        user_parts.append("Fix the issue. Use request_info if you need more files.")

    user_parts.append(
        "\nOutput JSON for the patch, then the COMPLETE new file content in a code block."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]

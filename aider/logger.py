import os
from datetime import datetime

from .config import LOG_DIR, ensure_dirs


class Logger:
    def __init__(self, task_id: str):
        ensure_dirs()
        self.task_id = task_id
        self.path = os.path.join(LOG_DIR, f"{task_id}.log")
        self._file = open(self.path, "w")
        self._write("LOG", f"task_id={task_id}")

    def _write(self, kind: str, msg: str):
        ts = datetime.utcnow().isoformat()
        line = f"[{ts}] {kind} {msg}\n"
        self._file.write(line)
        self._file.flush()

    def task(self, goal: str, project_path: str):
        self._write("TASK", f'"{goal}" project={project_path}')

    def retrieve(self, files: int, tokens: int):
        self._write("RETRIEVE", f"files={files} tokens={tokens}")

    def llm_call(self, model: str, prompt_tokens: int, output_tokens: int):
        self._write("LLM", f"model={model} prompt_tokens={prompt_tokens} output_tokens={output_tokens}")

    def patch(self, file_path: str, added: int, removed: int):
        self._write("PATCH", f"file={file_path} lines=+{added}/-{removed}")

    def validate(self, status_: str, details: str = ""):
        self._write("VALIDATE", f"status={status_}{' ' + details if details else ''}")

    def execute(self, command: str, exit_code: int):
        self._write("EXECUTE", f'command="{command}" exit={exit_code}')

    def test(self, passed: int, failed: int, command: str):
        self._write("TEST", f"passed={passed} failed={failed} command=\"{command}\"")

    def result(self, status_: str, retries: int, duration: float):
        self._write("RESULT", f"status={status_} retries={retries} duration={duration:.1f}")

    def error(self, stage: str, message: str):
        self._write("ERROR", f"stage={stage} {message}")

    def close(self):
        self._file.close()

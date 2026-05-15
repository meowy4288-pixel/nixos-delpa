import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Task:
    goal: str
    project_path: str
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    constraints: list[str] = field(default_factory=list)

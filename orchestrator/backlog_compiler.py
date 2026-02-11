from pathlib import Path
import re
import subprocess
from datetime import datetime

BACKLOG = Path("tasks/backlog.md")
TASKS = Path("tasks")
TEMPLATE = TASKS / "task_template.md"
GEMINI_CMD = ["gemini", "cli"]


def run_gemini(prompt: str) -> str:
    p = subprocess.run(
        GEMINI_CMD,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=300,
    )
    return p.stdout.strip()


def next_task_id():
    existing = [
        int(m.group(1))
        for f in TASKS.glob("*.md")
        if (m := re.match(r"(\d+)_", f.name))
    ]
    return f"{max(existing, default=0) + 1:03d}"


def compile_tasks():
    backlog = BACKLOG.read_text()
    template = TEMPLATE.read_text()

    prompt = f"""
You are a task compiler.

INPUT:
- A backlog with high-level items
- A task template that defines the required structure

INSTRUCTIONS:
- Convert each backlog item into ONE concrete task
- Fill in the task template completely
- Be explicit about scope, constraints, and acceptance criteria
- Do NOT invent new objectives

BACKLOG:
{backlog}

TASK TEMPLATE:
{template}
"""

    output = run_gemini(prompt)

    tasks = re.split(r"\n(?=# Task )", output)

    for task in tasks:
        if not task.strip():
            continue

        tid = next_task_id()
        title_line = task.splitlines()[0]
        slug = title_line.lower().replace(" ", "_").replace("#", "").strip()
        fname = TASKS / f"{tid}_{slug}.md"

        fname.write_text(task)
        print(f"Generated task: {fname}")


if __name__ == "__main__":
    compile_tasks()
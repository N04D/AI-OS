import subprocess
from pathlib import Path

PROMPTS_DIR = Path("../prompts")

def load_prompt(name):
    return (PROMPTS_DIR / name).read_text()

def run_llm(cmd, prompt):
    result = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()

def generate_commit_summary(task_text, eval_log, diff):
    template = load_prompt("commit_summary.md")
    prompt = template \
        .replace("{{ task_text }}", task_text) \
        .replace("{{ eval_log }}", eval_log) \
        .replace("{{ diff }}", diff)

    return run_llm(["gemini", "cli"], prompt)

def format_commit_message(summary, task_id):
    template = load_prompt("commit_formatter.md")
    prompt = template \
        .replace("{{ summary }}", summary) \
        .replace("{{ TASK_ID }}", task_id)

    return run_llm(["codex", "cli"], prompt)

import re

file_path = r"database\migrations\versions\0001_initial_schema.py"

with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# Replace server_default="QUEUED" with server_default=sa.text("'QUEUED'::task_status")
text = text.replace('server_default="QUEUED"', "server_default=sa.text(\"'QUEUED'::task_status\")")
text = text.replace('server_default="RUNNING"', "server_default=sa.text(\"'RUNNING'::run_status\")")
text = text.replace('server_default="running"', "server_default=sa.text(\"'running'::pipeline_status\")")
# 'task_status', 'run_status', 'pipeline_status' are the main enums with defaults.
# Also check for others.
# Are there other enums with defaults?
# Let's search inside text for `Enum(` lines.

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Updated 0001_initial_schema.py defaults.")

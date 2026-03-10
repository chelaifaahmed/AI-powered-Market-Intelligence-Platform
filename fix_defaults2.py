import re

file_path = r"database\migrations\versions\0001_initial_schema.py"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# Replace server_default="SOMETHING" with server_default=sa.text("'SOMETHING'")
# This avoids PostgreSQL strictly rejecting the string as an unknown enum during CREATE TABLE
text = re.sub(r'server_default="([^"]+)"', r'server_default=sa.text("\'\1\'")', text)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Applied sa.text() to all string server_defaults.")

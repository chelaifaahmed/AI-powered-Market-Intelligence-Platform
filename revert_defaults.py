import re

file_path = r"database\migrations\versions\0001_initial_schema.py"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# Let's cleanly revert to the original strings but ensure they match EXACTLY what's in the python class
# Removing sa.text("'*'::*")
text = re.sub(r'server_default=sa\.text\("(\'[^\']+\')::[^"]+"\)', r'server_default=\1', text)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Reverted explicit casts.")

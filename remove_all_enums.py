import re

file_path = r"database\migrations\versions\0001_initial_schema.py"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# Replace all instances of `sa.Enum(name="<anything>", create_type=True)` with `sa.String(50)`
text = re.sub(r'sa\.Enum\(name="[^"]+", create_type=True\)', r'sa.String(50)', text)
text = re.sub(r"sa\.Enum\(name='[^']+', create_type=True\)", r'sa.String(50)', text)

# Just in case `create_type=False` was still around
text = re.sub(r'sa\.Enum\(name="[^"]+", create_type=False\)', r'sa.String(50)', text)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Replaced all Enums with String(50).")

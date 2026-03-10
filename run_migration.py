"""Run migration and save error to file."""
import subprocess
import sys
import os

os.chdir(r"c:\Users\LENOVO\Documents\WebScrapper_PFE_Antigravity")

r = subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    capture_output=True,
    encoding="utf-8",
    errors="replace",
)

combined = r.stdout + r.stderr

with open(r"C:\Users\LENOVO\Documents\WebScrapper_PFE_Antigravity\alembic_err.txt", "w", encoding="utf-8") as f:
    f.write(f"RC={r.returncode}\n")
    f.write(combined)

print(f"RC={r.returncode}")
# Print lines that contain error context but strip File/line number noise
all_lines = combined.split("\n")
in_error = False
for line in all_lines:
    stripped = line.strip()
    if "sqlalchemy" in stripped.lower() or "psycopg" in stripped.lower() or "error" in stripped.lower() or "detail" in stripped.lower() or "hint" in stripped.lower() or "FAILED" in stripped:
        in_error = True
    if in_error and stripped:
        # Ascii-only to avoid encoding issues  
        safe = stripped.encode("ascii", errors="replace").decode("ascii")
        print(safe[:300])
        if len(safe) < 5:
            in_error = False

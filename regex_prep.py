import re

with open(r"database\migrations\versions\0001_initial_schema.py", "r", encoding="utf-8") as file:
    content = file.read()

# Alembic's create_table sa.Enum creates ENUM types in PostgreSQL. 
# However, mapping default values like server_default="QUEUED" for a PostgreSQL enum requires explicit casting 
# if the enum was created by SQLAlchemy: `server_default=sa.text("'QUEUED'::task_status")`.
# Or we can simply use the enum names without explicit creation since they're natively created.
# Let's add the explicit cast.

content = re.sub(r'server_default="([^"]+)"(.*?)', r"server_default='\1'", content)
# Wait, string regex replacing blindly is risky. 
# Let's adjust ENUM declarations.

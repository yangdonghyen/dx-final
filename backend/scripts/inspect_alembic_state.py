"""Read-only check of the DB migration state. Prints no credentials and changes nothing.

Run from the backend folder:
    C:\\dev\\프로젝트백엔드\\.venv\\Scripts\\python.exe scripts\\inspect_alembic_state.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text  # noqa: E402

from app.db.session import get_engine  # noqa: E402

engine = get_engine()
with engine.connect() as connection:
    versions = [row[0] for row in connection.execute(text("SELECT version_num FROM alembic_version"))]
    print("alembic_version:", versions)

    inspector = inspect(connection)
    tables = sorted(inspector.get_table_names())
    print("table count:", len(tables))
    print("tables:", ", ".join(tables))

    for table in ("trip_companions", "places", "trip_share_links", "youtube_saved_discoveries"):
        if table in tables:
            print(f"{table} columns:", ", ".join(column["name"] for column in inspector.get_columns(table)))
        else:
            print(f"{table}: (없음)")

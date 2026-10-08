"""Read-only comparison of the existing MySQL schema with the 22 service models.

Run from the project root: python -m scripts.verify_db_schema
This command never runs migrations and never reads service row contents.
"""
import json
import logging
import re

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Boolean, CheckConstraint, UniqueConstraint, inspect, text
from sqlalchemy.dialects.mysql import dialect

import app.models
from app.core.config import PROJECT_ROOT
from app.db.base import Base
from app.db.session import get_engine


def normalize_type(value):
    return re.sub(r"\s+", "", str(value)).upper().replace("INTEGER", "INT").replace("NUMERIC", "DECIMAL")


def normalize_default(value):
    if value is None:
        return None
    value = str(value).replace("'", "").replace('"', '').lower()
    value = value.replace("current_timestamp()", "current_timestamp")
    return {"true": "1", "false": "0"}.get(value, value)


def normalize_check(value):
    return re.sub(r"[\s`()]+", "", str(value)).lower()


def verify_schema(connection):
    """Return schema-only evidence. Do not fetch user or application data."""
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    expected = Base.metadata.tables
    issues = []
    counts = {"columns": 0, "primary_keys": 0, "foreign_keys": 0, "unique_constraints": 0,
              "check_constraints": 0, "enum_columns": 0, "json_columns": 0}

    def check(condition, message):
        if not condition:
            issues.append(message)

    check(tables == set(expected) | {"alembic_version"}, "Table set differs from models plus alembic_version")
    for name, table in expected.items():
        if name not in tables:
            issues.append(f"{name}: missing table")
            continue
        actual_columns = {c["name"]: c for c in inspector.get_columns(name)}
        check(set(actual_columns) == set(table.c.keys()), f"{name}: column set")
        for column in table.c:
            actual = actual_columns.get(column.name)
            if actual is None:
                continue
            label = f"{name}.{column.name}"
            counts["columns"] += 1
            expected_type = "TINYINT(1)" if isinstance(column.type, Boolean) else normalize_type(column.type.compile(dialect=dialect()))
            actual_type = normalize_type(actual["type"].compile(dialect=dialect()))
            check(actual_type == expected_type, label + ": type")
            check(actual["nullable"] == column.nullable, label + ": nullability")
            default = column.server_default.arg if column.server_default is not None else None
            check(normalize_default(actual.get("default")) == normalize_default(default), label + ": server default/update")
            if column.autoincrement is True:
                check(actual.get("autoincrement") is True, label + ": auto increment")
            if hasattr(column.type, "enums"):
                counts["enum_columns"] += 1
                check(actual["type"].enums == column.type.enums, label + ": enum values/order")
            if expected_type == "JSON":
                counts["json_columns"] += 1
        check(inspector.get_pk_constraint(name)["constrained_columns"] == list(table.primary_key.columns.keys()), name + ": primary key")
        counts["primary_keys"] += 1
        actual_unique = {c["name"]: tuple(c["column_names"]) for c in inspector.get_unique_constraints(name)}
        expected_unique = {c.name: tuple(c.columns.keys()) for c in table.constraints if isinstance(c, UniqueConstraint)}
        check(actual_unique == expected_unique, name + ": unique constraints")
        counts["unique_constraints"] += len(actual_unique)
        actual_fk = {
            c["name"]: (tuple(c["constrained_columns"]), c["referred_table"], tuple(c["referred_columns"]), c["options"].get("ondelete", "RESTRICT"))
            for c in inspector.get_foreign_keys(name)
        }
        expected_fk = {
            c.name: (tuple(c.columns.keys()), c.referred_table.name, tuple(fk.column.name for fk in c.elements), c.ondelete)
            for c in table.foreign_key_constraints
        }
        check(actual_fk == expected_fk, name + ": foreign keys / ondelete")
        counts["foreign_keys"] += len(actual_fk)
        actual_checks = {c["name"]: normalize_check(c["sqltext"]) for c in inspector.get_check_constraints(name)}
        expected_checks = {c.name: normalize_check(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)}
        check(actual_checks == expected_checks, name + ": check constraints")
        counts["check_constraints"] += len(actual_checks)

    options = connection.execute(text(
        "SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE()"
    ))
    for name, engine, collation in options:
        if name in expected:
            check(engine == "InnoDB" and collation.startswith("utf8mb4_"), name + ": engine/charset")
    enforced = connection.execute(text(
        "SELECT CONSTRAINT_NAME, ENFORCED FROM information_schema.TABLE_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA = DATABASE() AND CONSTRAINT_TYPE = 'CHECK'"
    )).all()
    check(all(row[1] == "YES" for row in enforced), "A check constraint is not enforced")
    versions = list(connection.execute(text("SELECT version_num FROM alembic_version")).scalars()) if "alembic_version" in tables else []
    heads = ScriptDirectory.from_config(Config(str(PROJECT_ROOT / "alembic.ini"))).get_heads()
    check(versions == heads, "Alembic version differs from migration head")
    return {
        "database": connection.execute(text("SELECT DATABASE()")).scalar_one(),
        "mysql_version": connection.execute(text("SELECT VERSION()")).scalar_one(),
        "tables": sorted(tables), "service_table_count": len(tables - {"alembic_version"}),
        "alembic_version": versions, "verified": counts, "issues": issues,
    }


def main():
    logging.disable(logging.CRITICAL)
    engine = None
    try:
        engine = get_engine()
        with engine.connect() as connection:
            result = verify_schema(connection)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 1 if result["issues"] else 0
    except Exception as exc:
        original = getattr(exc, "orig", exc)
        args = getattr(original, "args", ())
        # Raw exception text can contain connection details. Never print it here.
        print(json.dumps({"error_type": type(original).__name__,
                          "code": args[0] if args and isinstance(args[0], int) else None}))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

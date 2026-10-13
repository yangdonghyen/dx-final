"""Check the models against the SQL in the unchanged source-of-truth document."""
import re

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.orm import configure_mappers

import app.models
from app.core.config import PROJECT_ROOT
from app.db.base import Base

DOCUMENT = (PROJECT_ROOT / "docs/03_database/03_db_schema.md").read_text(encoding="utf-8")
SCHEMA = dict(re.findall(r"CREATE TABLE (\w+) \((.*?)\) ENGINE=InnoDB;", DOCUMENT, re.S))


def normalize_type(value):
    value = re.sub(r"\s+", "", value).upper()
    if value == "BOOL":
        return "BOOLEAN"
    return value.replace("INTEGER", "INT").replace("NUMERIC", "DECIMAL")


def test_exact_service_table_set_and_mappers():
    assert len(SCHEMA) == 25
    # Later migrations add service tables before the source document is revised.
    assert set(SCHEMA) <= set(Base.metadata.tables)
    configure_mappers()
    assert len(Base.registry.mappers) == len(Base.metadata.tables)
    for mapper in Base.registry.mappers:
        for relation in mapper.relationships:
            assert not relation.cascade.delete
            assert not relation.cascade.delete_orphan
            assert not relation.uselist


@pytest.mark.parametrize("table_name", SCHEMA)
def test_every_column_type_nullability_pk_default_and_enum(table_name):
    body = SCHEMA[table_name]
    columns = re.findall(
        r"^    (\w+) (ENUM\([^)]*\)|VARCHAR\(\d+\)|DECIMAL\(\d+,\d+\)|INT UNSIGNED|BIGINT|INT|BOOLEAN|DATETIME|DATE|TIME|TEXT|JSON)"
        r"([^\n]*(?:\n        ON UPDATE CURRENT_TIMESTAMP)?)",
        body, re.M,
    )
    table = Base.metadata.tables[table_name]
    assert list(table.columns.keys()) == [column[0] for column in columns]
    for name, sql_type, flags in columns:
        column = table.c[name]
        assert normalize_type(str(column.type.compile(dialect=dialect()))) == normalize_type(sql_type), name
        pk = "PRIMARY KEY" in flags
        assert column.primary_key == pk, name
        assert column.nullable == (not pk and "NOT NULL" not in flags), name
        if "AUTO_INCREMENT" in flags:
            assert column.autoincrement is True, name
        default = re.search(r"DEFAULT ('.*?'|\w+)(?:\s+ON UPDATE (\w+))?", flags)
        expected = (default[1] + (" ON UPDATE " + default[2] if default[2] else "")) if default else None
        assert (str(column.server_default.arg) if column.server_default else None) == expected, name
        if sql_type.startswith("ENUM"):
            assert column.type.enums == re.findall(r"'([^']*)'", sql_type)
            processor = column.type.bind_processor(dialect())
            with pytest.raises(LookupError):
                processor("NOT_A_DOCUMENTED_ENUM_VALUE")
    assert table.dialect_options["mysql"]["engine"] == "InnoDB"
    assert table.dialect_options["mysql"]["charset"] == "utf8mb4"


@pytest.mark.parametrize("table_name", SCHEMA)
def test_all_foreign_unique_and_check_constraints_match_document(table_name):
    body = SCHEMA[table_name]
    table = Base.metadata.tables[table_name]
    expected_unique = {
        name: tuple(c.strip() for c in columns.split(","))
        for name, columns in re.findall(r"CONSTRAINT (\w+)\s+UNIQUE \((.*?)\)", body, re.S)
    }
    actual_unique = {c.name: tuple(c.columns.keys()) for c in table.constraints if isinstance(c, UniqueConstraint)}
    assert actual_unique == expected_unique
    expected_fk = {
        name: (column, parent + "." + target, ondelete)
        for name, column, parent, target, ondelete in re.findall(
            r"CONSTRAINT (\w+)\s+FOREIGN KEY \((\w+)\)\s+REFERENCES (\w+)\((\w+)\)\s+ON DELETE (CASCADE|SET NULL|RESTRICT)", body)
    }
    actual_fk = {fk.name: (fk.parent.name, fk.target_fullname, fk.ondelete) for fk in table.foreign_keys}
    assert actual_fk == expected_fk
    expected_checks = {name: " ".join(expression.split()) for name, expression in re.findall(
        r"CONSTRAINT (\w+)\s+CHECK \((.*?)\)", body, re.S)}
    actual_checks = {c.name: " ".join(str(c.sqltext).split()) for c in table.constraints if isinstance(c, CheckConstraint)}
    assert actual_checks == expected_checks
    assert not table.indexes  # No undocumented additional indexes.


def test_specific_unique_and_sensitive_column_rules():
    tables = Base.metadata.tables
    for table, column in [("users", "nickname"), ("places", "name")]:
        assert all(tuple(c.columns.keys()) != (column,) for c in tables[table].constraints if isinstance(c, UniqueConstraint))
    required_unique = {
        "user_auths": ("provider", "provider_user_id"),
        "trip_preferences": ("trip_id",),
        "travel_plans": ("trip_id",),
        "places": ("kakao_place_id",),
        "plan_items": ("plan_id", "visit_date", "sequence_no"),
    }
    for name, columns in required_unique.items():
        assert columns in {tuple(c.columns.keys()) for c in tables[name].constraints if isinstance(c, UniqueConstraint)}
    assert "token_hash" in tables["refresh_tokens"].c
    assert "token" not in tables["refresh_tokens"].c
    assert "resolved_at" in tables["plan_validation_issues"].c
    assert "resolved" not in tables["plan_validation_issues"].c
    assert all("confidence" not in table.c for table in tables.values())
    assert all("image" not in name for name in tables["docent_analyses"].c.keys())


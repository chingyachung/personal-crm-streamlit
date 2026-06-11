from __future__ import annotations

from pathlib import Path
from datetime import datetime

from app.database.connection import get_connection


SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def init_database(database_path: Path) -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    connection = get_connection(database_path)
    try:
        connection.executescript(schema_sql)
        _ensure_column(connection, "customers", "raw_json", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "customers", "raw_text", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "customers", "follow_up_date", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "customers", "last_contact_date", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "customers", "appointment_date", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "customers", "appointment_at", "TEXT NOT NULL DEFAULT ''")
        _migrate_appointment_date_to_datetime(connection)
        _seed_activity_history_from_current_summary(connection)
        connection.commit()
    finally:
        connection.close()


def _ensure_column(connection, table_name: str, column_name: str, column_definition: str) -> None:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_columns = {row["name"] for row in rows}
    if column_name not in existing_columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def _migrate_appointment_date_to_datetime(connection) -> None:
    rows = connection.execute("PRAGMA table_info(customers)").fetchall()
    existing_columns = {row["name"] for row in rows}
    if "appointment_date" not in existing_columns or "appointment_at" not in existing_columns:
        return

    connection.execute(
        """
        UPDATE customers
        SET appointment_at = appointment_date || ' 09:00:00'
        WHERE appointment_date != ''
          AND appointment_at = ''
        """
    )


def _seed_activity_history_from_current_summary(connection) -> None:
    rows = connection.execute(
        """
        SELECT id, last_contact_date, follow_up_date, appointment_at
        FROM customers
        """
    ).fetchall()

    mapping = (
        ("contact", "completed", "last_contact_date"),
        ("follow_up", "scheduled", "follow_up_date"),
        ("appointment", "scheduled", "appointment_at"),
    )

    for row in rows:
        customer_id = row["id"]
        for activity_type, status, column_name in mapping:
            raw_value = (row[column_name] or "").strip()
            activity_datetime = _normalize_activity_datetime(raw_value)
            if not activity_datetime:
                continue

            exists = connection.execute(
                """
                SELECT 1
                FROM activity_history
                WHERE customer_id = ?
                  AND activity_type = ?
                  AND activity_datetime = ?
                  AND status = ?
                LIMIT 1
                """,
                (customer_id, activity_type, activity_datetime, status),
            ).fetchone()
            if exists:
                continue

            connection.execute(
                """
                INSERT INTO activity_history (
                    customer_id,
                    activity_type,
                    activity_datetime,
                    status,
                    title,
                    note
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (customer_id, activity_type, activity_datetime, status, "", ""),
            )


def _normalize_activity_datetime(raw_value: str) -> str:
    if not raw_value:
        return ""

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw_value, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    try:
        return f"{datetime.fromisoformat(raw_value).date().isoformat()} 00:00:00"
    except ValueError:
        return ""

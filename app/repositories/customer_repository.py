from __future__ import annotations

import sqlite3
from typing import Optional

from app.models.activity_history import ActivityHistoryEntry
from app.models.contact_history import ContactHistoryEntry
from app.models.customer import Customer


class CustomerRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_customers(
        self,
        *,
        search: str = "",
        status: str = "",
        tag: str = "",
    ) -> list[Customer]:
        query = """
            SELECT *
            FROM customers
            WHERE 1 = 1
        """
        params: list[str] = []

        if search:
            like_value = f"%{search.strip()}%"
            query += """
                AND (
                    name LIKE ?
                    OR email LIKE ?
                    OR message LIKE ?
                    OR raw_text LIKE ?
                )
            """
            params.extend([like_value, like_value, like_value, like_value])

        if status:
            query += " AND status = ?"
            params.append(status)

        if tag:
            query += " AND tags LIKE ?"
            params.append(f"%{tag}%")

        query += " ORDER BY datetime(timestamp) DESC, id DESC"
        rows = self.connection.execute(query, params).fetchall()
        return [self._row_to_customer(row) for row in rows]

    def get_by_id(self, customer_id: int) -> Optional[Customer]:
        row = self.connection.execute(
            "SELECT * FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
        return self._row_to_customer(row) if row else None

    def get_by_form_submission_id(self, form_submission_id: str) -> Optional[Customer]:
        row = self.connection.execute(
            "SELECT * FROM customers WHERE form_submission_id = ?",
            (form_submission_id,),
        ).fetchone()
        return self._row_to_customer(row) if row else None

    def list_form_submission_ids(self) -> set[str]:
        rows = self.connection.execute(
            "SELECT form_submission_id FROM customers"
        ).fetchall()
        return {row["form_submission_id"] for row in rows}

    def delete_customers_not_in_submission_ids(self, active_submission_ids: set[str]) -> int:
        if not active_submission_ids:
            cursor = self.connection.execute("DELETE FROM customers")
            self.connection.commit()
            return cursor.rowcount

        placeholders = ", ".join("?" for _ in active_submission_ids)
        cursor = self.connection.execute(
            f"DELETE FROM customers WHERE form_submission_id NOT IN ({placeholders})",
            tuple(active_submission_ids),
        )
        self.connection.commit()
        return cursor.rowcount

    def create(self, customer: Customer) -> Customer:
        cursor = self.connection.execute(
            """
            INSERT INTO customers (
                form_submission_id,
                timestamp,
                name,
                email,
                message,
                raw_json,
                raw_text,
                notes,
                status,
                tags,
                follow_up_date,
                last_contact_date,
                appointment_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer.form_submission_id,
                customer.timestamp,
                customer.name,
                customer.email,
                customer.message,
                customer.raw_json,
                customer.raw_text,
                customer.notes,
                customer.status,
                customer.tags,
                customer.follow_up_date,
                customer.last_contact_date,
                customer.appointment_at,
            ),
        )
        self.connection.commit()
        return self.get_by_id(cursor.lastrowid)

    def update_internal_fields(
        self,
        customer_id: int,
        *,
        notes: str,
        status: str,
        tags: str,
        follow_up_date: str,
        last_contact_date: str,
        appointment_at: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE customers
            SET notes = ?, status = ?, tags = ?, follow_up_date = ?, last_contact_date = ?, appointment_at = ?
            WHERE id = ?
            """,
            (notes, status, tags, follow_up_date, last_contact_date, appointment_at, customer_id),
        )
        self.connection.commit()

    def list_customers_with_appointment_between(
        self,
        *,
        start_date: str,
        end_date: str,
    ) -> list[Customer]:
        rows = self.connection.execute(
            """
            SELECT *
            FROM customers
            WHERE appointment_at != ''
              AND appointment_at >= ?
              AND appointment_at <= ?
            ORDER BY appointment_at ASC, id ASC
            """,
            (start_date, end_date),
        ).fetchall()
        return [self._row_to_customer(row) for row in rows]

    def list_contact_history(self, customer_id: int) -> list[ContactHistoryEntry]:
        rows = self.connection.execute(
            """
            SELECT *
            FROM contact_history
            WHERE customer_id = ?
            ORDER BY contact_date DESC, id DESC
            """,
            (customer_id,),
        ).fetchall()
        return [self._row_to_contact_history(row) for row in rows]

    def add_contact_history(self, customer_id: int, *, contact_date: str, note: str) -> None:
        self.connection.execute(
            """
            INSERT INTO contact_history (customer_id, contact_date, note)
            VALUES (?, ?, ?)
            """,
            (customer_id, contact_date, note),
        )
        self.connection.commit()

    def delete_contact_history(self, entry_id: int) -> None:
        self.connection.execute(
            "DELETE FROM contact_history WHERE id = ?",
            (entry_id,),
        )
        self.connection.commit()

    def list_activity_history(self, customer_id: int) -> list[ActivityHistoryEntry]:
        rows = self.connection.execute(
            """
            SELECT *
            FROM activity_history
            WHERE customer_id = ?
            ORDER BY activity_datetime DESC, id DESC
            """,
            (customer_id,),
        ).fetchall()
        return [self._row_to_activity_history(row) for row in rows]

    def add_activity_history(
        self,
        customer_id: int,
        *,
        activity_type: str,
        activity_datetime: str,
        title: str,
        note: str,
        status: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO activity_history (
                customer_id,
                activity_type,
                activity_datetime,
                title,
                note,
                status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (customer_id, activity_type, activity_datetime, title, note, status),
        )
        self.connection.commit()

    def get_dashboard_counts(self) -> dict[str, int]:
        total = self.connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        open_count = self.connection.execute(
            "SELECT COUNT(*) FROM customers WHERE status = ?",
            ("Open",),
        ).fetchone()[0]
        vip_count = self.connection.execute(
            "SELECT COUNT(*) FROM customers WHERE lower(tags) LIKE ?",
            ("%vip%",),
        ).fetchone()[0]
        hot_lead_count = self.connection.execute(
            "SELECT COUNT(*) FROM customers WHERE lower(tags) LIKE ?",
            ("%hot lead%",),
        ).fetchone()[0]
        return {
            "total_customers": total,
            "open_customers": open_count,
            "vip_customers": vip_count,
            "hot_leads": hot_lead_count,
        }

    def list_statuses(self) -> list[str]:
        rows = self.connection.execute(
            "SELECT DISTINCT status FROM customers WHERE status != '' ORDER BY status"
        ).fetchall()
        return [row["status"] for row in rows]

    def list_tags(self) -> list[str]:
        rows = self.connection.execute("SELECT tags FROM customers WHERE tags != ''").fetchall()
        tags: set[str] = set()
        for row in rows:
            tags.update(self._split_tags(row["tags"]))
        return sorted(tags)

    @staticmethod
    def _split_tags(raw_tags: str) -> list[str]:
        return [tag.strip() for tag in raw_tags.split(",") if tag.strip()]

    @staticmethod
    def _row_to_customer(row: sqlite3.Row) -> Customer:
        return Customer(
            id=row["id"],
            form_submission_id=row["form_submission_id"],
            timestamp=row["timestamp"] or "",
            name=row["name"],
            email=row["email"],
            message=row["message"],
            raw_json=row["raw_json"],
            raw_text=row["raw_text"],
            notes=row["notes"],
            status=row["status"],
            tags=row["tags"],
            follow_up_date=row["follow_up_date"] or "",
            last_contact_date=row["last_contact_date"] or "",
            appointment_at=(row["appointment_at"] or row["appointment_date"] or ""),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_contact_history(row: sqlite3.Row) -> ContactHistoryEntry:
        return ContactHistoryEntry(
            id=row["id"],
            customer_id=row["customer_id"],
            contact_date=row["contact_date"],
            note=row["note"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_activity_history(row: sqlite3.Row) -> ActivityHistoryEntry:
        return ActivityHistoryEntry(
            id=row["id"],
            customer_id=row["customer_id"],
            activity_type=row["activity_type"],
            activity_datetime=row["activity_datetime"],
            title=row["title"],
            note=row["note"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

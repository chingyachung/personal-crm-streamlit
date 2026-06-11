from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.database.connection import get_connection
from app.database.init_db import init_database
from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository
from app.services.customer_service import CustomerService


class ActivityHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "activity.sqlite3"
        init_database(self.database_path)
        self.connection = get_connection(self.database_path)
        self.repository = CustomerRepository(self.connection)
        self.service = CustomerService(self.repository)
        self.customer = self._create_customer()

    def tearDown(self) -> None:
        self.connection.close()
        self.temp_dir.cleanup()

    def test_updating_last_contact_appends_completed_contact_activity(self) -> None:
        self.service.update_internal_fields(
            self.customer.id,
            notes=self.customer.notes,
            status=self.customer.status,
            tags=self.customer.tags,
            follow_up_date=self.customer.follow_up_date,
            last_contact_date="2026-06-12",
            appointment_at=self.customer.appointment_at,
        )

        entries = self.service.list_activity_history(self.customer.id)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].activity_type, "contact")
        self.assertEqual(entries[0].activity_datetime, "2026-06-12 00:00:00")
        self.assertEqual(entries[0].status, "completed")

    def test_updating_follow_up_appends_scheduled_follow_up_activity(self) -> None:
        self.service.update_internal_fields(
            self.customer.id,
            notes=self.customer.notes,
            status=self.customer.status,
            tags=self.customer.tags,
            follow_up_date="2026-06-25",
            last_contact_date=self.customer.last_contact_date,
            appointment_at=self.customer.appointment_at,
        )

        entries = self.service.list_activity_history(self.customer.id)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].activity_type, "follow_up")
        self.assertEqual(entries[0].activity_datetime, "2026-06-25 00:00:00")
        self.assertEqual(entries[0].status, "scheduled")

    def test_updating_appointment_appends_scheduled_appointment_activity(self) -> None:
        self.service.update_internal_fields(
            self.customer.id,
            notes=self.customer.notes,
            status=self.customer.status,
            tags=self.customer.tags,
            follow_up_date=self.customer.follow_up_date,
            last_contact_date=self.customer.last_contact_date,
            appointment_at="2026-06-20 10:00:00",
        )

        entries = self.service.list_activity_history(self.customer.id)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].activity_type, "appointment")
        self.assertEqual(entries[0].activity_datetime, "2026-06-20 10:00:00")
        self.assertEqual(entries[0].status, "scheduled")

    def test_removing_summary_field_keeps_existing_activity_history(self) -> None:
        self.service.update_internal_fields(
            self.customer.id,
            notes=self.customer.notes,
            status=self.customer.status,
            tags=self.customer.tags,
            follow_up_date=self.customer.follow_up_date,
            last_contact_date=self.customer.last_contact_date,
            appointment_at="2026-06-20 10:00:00",
        )

        self.service.update_internal_fields(
            self.customer.id,
            notes=self.customer.notes,
            status=self.customer.status,
            tags=self.customer.tags,
            follow_up_date=self.customer.follow_up_date,
            last_contact_date=self.customer.last_contact_date,
            appointment_at="",
        )

        entries = self.service.list_activity_history(self.customer.id)
        updated_customer = self.service.get_customer(self.customer.id)

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].activity_type, "appointment")
        self.assertEqual(entries[0].status, "cancelled")
        self.assertEqual(entries[0].activity_datetime, "2026-06-20 10:00:00")
        self.assertEqual(entries[1].activity_type, "appointment")
        self.assertEqual(entries[1].status, "scheduled")
        self.assertIsNotNone(updated_customer)
        self.assertEqual(updated_customer.appointment_at, "")

    def test_existing_summary_values_are_seeded_into_activity_history_on_init(self) -> None:
        seeded_customer = self._create_customer_with_fields(
            form_submission_id="seeded",
            follow_up_date="2026-06-13",
            last_contact_date="2026-06-11",
            appointment_at="2026-06-26 10:00:00",
        )

        init_database(self.database_path)

        seeded_entries = self.service.list_activity_history(seeded_customer.id)
        normalized = {(entry.activity_type, entry.activity_datetime, entry.status) for entry in seeded_entries}

        self.assertIn(("contact", "2026-06-11 00:00:00", "completed"), normalized)
        self.assertIn(("follow_up", "2026-06-13 00:00:00", "scheduled"), normalized)
        self.assertIn(("appointment", "2026-06-26 10:00:00", "scheduled"), normalized)

    def _create_customer(self) -> Customer:
        return self._create_customer_with_fields()

    def _create_customer_with_fields(
        self,
        *,
        form_submission_id: str = "activity-1",
        follow_up_date: str = "",
        last_contact_date: str = "",
        appointment_at: str = "",
    ) -> Customer:
        customer = Customer(
            id=None,
            form_submission_id=form_submission_id,
            timestamp="2026-06-11 10:00:00",
            name="Activity Customer",
            email=f"{form_submission_id}@example.com",
            message="Hello",
            raw_json="{}",
            raw_text="",
            notes="",
            status="Open",
            tags="",
            follow_up_date=follow_up_date,
            last_contact_date=last_contact_date,
            appointment_at=appointment_at,
        )
        return self.repository.create(customer)


if __name__ == "__main__":
    unittest.main()

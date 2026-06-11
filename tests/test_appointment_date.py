from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.database.connection import get_connection
from app.database.init_db import init_database
from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository
from app.services.customer_service import CustomerService


class AppointmentDateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.sqlite3"
        init_database(self.database_path)
        self.connection = get_connection(self.database_path)
        self.repository = CustomerRepository(self.connection)
        self.service = CustomerService(self.repository)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp_dir.cleanup()

    def test_create_customer_with_appointment_date(self) -> None:
        customer = self._create_customer(appointment_at="2026-06-20 14:00:00")
        saved = self.repository.get_by_id(customer.id)

        self.assertIsNotNone(saved)
        self.assertEqual(saved.appointment_at, "2026-06-20 14:00:00")

    def test_update_appointment_date(self) -> None:
        customer = self._create_customer()

        self.service.update_internal_fields(
            customer.id,
            notes=customer.notes,
            status=customer.status,
            tags=customer.tags,
            follow_up_date=customer.follow_up_date,
            last_contact_date=customer.last_contact_date,
            appointment_at="2026-06-21 09:30:00",
        )

        updated = self.service.get_customer(customer.id)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.appointment_at, "2026-06-21 09:30:00")

    def test_remove_appointment_date(self) -> None:
        customer = self._create_customer(appointment_at="2026-06-22 16:00:00")

        self.service.update_internal_fields(
            customer.id,
            notes=customer.notes,
            status=customer.status,
            tags=customer.tags,
            follow_up_date=customer.follow_up_date,
            last_contact_date=customer.last_contact_date,
            appointment_at="",
        )

        updated = self.service.get_customer(customer.id)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.appointment_at, "")

    def test_dashboard_excludes_removed_appointment_date(self) -> None:
        today = f"{date.today().isoformat()} 10:00:00"
        upcoming = f"{(date.today() + timedelta(days=3)).isoformat()} 14:30:00"

        customer_today = self._create_customer(form_submission_id="today", appointment_at=today)
        customer_upcoming = self._create_customer(form_submission_id="upcoming", appointment_at=upcoming)

        todays_before = {customer.id for customer in self.service.get_todays_appointments()}
        upcoming_before = {customer.id for customer in self.service.get_upcoming_appointments(days_ahead=14)}

        self.assertIn(customer_today.id, todays_before)
        self.assertIn(customer_upcoming.id, upcoming_before)

        self.service.update_internal_fields(
            customer_today.id,
            notes=customer_today.notes,
            status=customer_today.status,
            tags=customer_today.tags,
            follow_up_date=customer_today.follow_up_date,
            last_contact_date=customer_today.last_contact_date,
            appointment_at="",
        )
        self.service.update_internal_fields(
            customer_upcoming.id,
            notes=customer_upcoming.notes,
            status=customer_upcoming.status,
            tags=customer_upcoming.tags,
            follow_up_date=customer_upcoming.follow_up_date,
            last_contact_date=customer_upcoming.last_contact_date,
            appointment_at="",
        )

        todays_after = {customer.id for customer in self.service.get_todays_appointments()}
        upcoming_after = {customer.id for customer in self.service.get_upcoming_appointments(days_ahead=14)}

        self.assertNotIn(customer_today.id, todays_after)
        self.assertNotIn(customer_upcoming.id, upcoming_after)

    def _create_customer(
        self,
        *,
        form_submission_id: str = "sub-1",
        appointment_at: str = "",
    ) -> Customer:
        customer = Customer(
            id=None,
            form_submission_id=form_submission_id,
            timestamp="2026-06-11 10:00:00",
            name=f"Customer {form_submission_id}",
            email=f"{form_submission_id}@example.com",
            message="Hello",
            raw_json="{}",
            raw_text="",
            notes="",
            status="Open",
            tags="",
            follow_up_date="",
            last_contact_date="",
            appointment_at=appointment_at,
        )
        return self.repository.create(customer)


if __name__ == "__main__":
    unittest.main()

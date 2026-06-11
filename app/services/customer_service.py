from __future__ import annotations

from datetime import date, datetime

from app.models.activity_history import ActivityHistoryEntry
from app.models.contact_history import ContactHistoryEntry
from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository


class CustomerService:
    STATUS_OPTIONS = ["Open", "In Progress", "Closed"]
    ACTIVITY_STATUS_BY_TYPE = {
        "contact": "completed",
        "follow_up": "scheduled",
        "appointment": "scheduled",
    }
    ACTIVITY_CANCELLED_BY_TYPE = {
        "contact": "cancelled",
        "follow_up": "cancelled",
        "appointment": "cancelled",
    }

    def __init__(self, repository: CustomerRepository) -> None:
        self.repository = repository

    def search_customers(self, *, search: str = "", status: str = "", tag: str = "") -> list[Customer]:
        return self.repository.list_customers(search=search, status=status, tag=tag)

    def get_customer(self, customer_id: int) -> Customer | None:
        return self.repository.get_by_id(customer_id)

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
        existing_customer = self.repository.get_by_id(customer_id)
        if existing_customer is None:
            return

        normalized_status = status if status in self.STATUS_OPTIONS else self.STATUS_OPTIONS[0]
        normalized_tags = ", ".join(tag.strip() for tag in tags.split(",") if tag.strip())
        self.repository.update_internal_fields(
            customer_id,
            notes=notes.strip(),
            status=normalized_status,
            tags=normalized_tags,
            follow_up_date=follow_up_date,
            last_contact_date=last_contact_date,
            appointment_at=appointment_at,
        )
        self._append_activity_if_changed(
            customer_id=customer_id,
            activity_type="contact",
            previous_value=existing_customer.last_contact_date,
            next_value=last_contact_date,
        )
        self._append_activity_if_changed(
            customer_id=customer_id,
            activity_type="follow_up",
            previous_value=existing_customer.follow_up_date,
            next_value=follow_up_date,
        )
        self._append_activity_if_changed(
            customer_id=customer_id,
            activity_type="appointment",
            previous_value=existing_customer.appointment_at,
            next_value=appointment_at,
        )

    def get_status_options(self) -> list[str]:
        existing = self.repository.list_statuses()
        ordered = [status for status in self.STATUS_OPTIONS if status in set(existing) or status in self.STATUS_OPTIONS]
        return ordered

    def get_available_tags(self) -> list[str]:
        return self.repository.list_tags()

    def list_contact_history(self, customer_id: int) -> list[ContactHistoryEntry]:
        return self.repository.list_contact_history(customer_id)

    def add_contact_history(self, customer_id: int, *, contact_date: str, note: str) -> None:
        normalized_note = note.strip()
        if not contact_date or not normalized_note:
            return
        self.repository.add_contact_history(
            customer_id,
            contact_date=contact_date,
            note=normalized_note,
        )

    def delete_contact_history(self, entry_id: int) -> None:
        self.repository.delete_contact_history(entry_id)

    def list_activity_history(self, customer_id: int) -> list[ActivityHistoryEntry]:
        return self.repository.list_activity_history(customer_id)

    def get_dashboard_stats(self) -> dict[str, int]:
        stats = self.repository.get_dashboard_counts()
        customers = self.repository.list_customers()
        today = date.today()
        start_of_week = today.fromordinal(today.toordinal() - today.weekday())
        new_this_week = 0
        for customer in customers:
            customer_date = self._customer_date(customer)
            if customer_date and customer_date >= start_of_week:
                new_this_week += 1
        stats["new_this_week"] = new_this_week
        return stats

    def get_todays_appointments(self) -> list[Customer]:
        today = date.today().isoformat()
        return self.repository.list_customers_with_appointment_between(
            start_date=f"{today} 00:00",
            end_date=f"{today} 23:59",
        )

    def get_upcoming_appointments(self, *, days_ahead: int = 14) -> list[Customer]:
        start_date = f"{date.today().fromordinal(date.today().toordinal() + 1).isoformat()} 00:00"
        end_date = f"{date.today().fromordinal(date.today().toordinal() + days_ahead).isoformat()} 23:59"
        return self.repository.list_customers_with_appointment_between(
            start_date=start_date,
            end_date=end_date,
        )

    @staticmethod
    def is_follow_up_due(follow_up_date: str) -> bool:
        if not follow_up_date:
            return False
        try:
            return date.fromisoformat(follow_up_date) <= date.today()
        except ValueError:
            return False

    @staticmethod
    def _customer_date(customer: Customer) -> date | None:
        candidates = [customer.timestamp, customer.created_at or ""]
        for raw_value in candidates:
            parsed = CustomerService._parse_date(raw_value)
            if parsed:
                return parsed
        return None

    @staticmethod
    def _parse_date(raw_value: str) -> date | None:
        if not raw_value:
            return None

        normalized = raw_value.strip()
        normalized = normalized.replace("上午", "AM").replace("下午", "PM")
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %p %I:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(normalized, fmt).date()
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(normalized).date()
        except ValueError:
            return None

    def _append_activity_if_changed(
        self,
        *,
        customer_id: int,
        activity_type: str,
        previous_value: str,
        next_value: str,
    ) -> None:
        normalized_previous = previous_value.strip()
        normalized_next = next_value.strip()
        if normalized_next == normalized_previous:
            return

        if normalized_previous and not normalized_next:
            self._append_activity(
                customer_id=customer_id,
                activity_type=activity_type,
                activity_datetime=normalized_previous,
                status=self.ACTIVITY_CANCELLED_BY_TYPE[activity_type],
            )
            return

        if not normalized_next:
            return

        self._append_activity(
            customer_id=customer_id,
            activity_type=activity_type,
            activity_datetime=normalized_next,
            status=self.ACTIVITY_STATUS_BY_TYPE[activity_type],
        )

    def _append_activity(
        self,
        *,
        customer_id: int,
        activity_type: str,
        activity_datetime: str,
        status: str,
    ) -> None:
        normalized_datetime = self._normalize_activity_datetime(activity_datetime)
        if not normalized_datetime:
            return

        self.repository.add_activity_history(
            customer_id,
            activity_type=activity_type,
            activity_datetime=normalized_datetime,
            title="",
            note="",
            status=status,
        )

    @staticmethod
    def _normalize_activity_datetime(raw_value: str) -> str:
        if not raw_value:
            return ""

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(raw_value, fmt).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

        parsed_date = CustomerService._parse_date(raw_value)
        if parsed_date:
            return f"{parsed_date.isoformat()} 00:00:00"
        return ""

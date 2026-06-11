from __future__ import annotations

from dataclasses import dataclass

from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository
from app.sync.google_sheets_client import GoogleSheetsClient


@dataclass(slots=True)
class SyncResult:
    fetched_count: int
    inserted_count: int
    skipped_count: int
    deleted_count: int


class SyncService:
    def __init__(self, sheets_client: GoogleSheetsClient, repository: CustomerRepository) -> None:
        self.sheets_client = sheets_client
        self.repository = repository

    def sync(self) -> SyncResult:
        # Customer records are managed by Google Sheets. To remove a customer,
        # delete the corresponding row in Google Sheets. The CRM will reflect
        # the change automatically after data synchronization.
        sheet_customers = self.sheets_client.fetch_customers()
        active_submission_ids = {customer.form_submission_id for customer in sheet_customers}
        new_customers: list[Customer] = []
        skipped_count = 0

        for customer in sheet_customers:
            existing = self.repository.get_by_form_submission_id(customer.form_submission_id)
            if existing:
                skipped_count += 1
                continue
            new_customers.append(customer)

        inserted_count = 0
        for customer in new_customers:
            self.repository.create(customer)
            inserted_count += 1

        deleted_count = self.repository.delete_customers_not_in_submission_ids(active_submission_ids)

        return SyncResult(
            fetched_count=len(sheet_customers),
            inserted_count=inserted_count,
            skipped_count=skipped_count,
            deleted_count=deleted_count,
        )

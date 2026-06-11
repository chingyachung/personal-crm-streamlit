from __future__ import annotations

from app.config import get_config
from app.database.connection import get_connection
from app.database.init_db import init_database
from app.repositories.customer_repository import CustomerRepository
from app.sync.google_sheets_client import GoogleSheetsClient
from app.sync.sync_service import SyncService


def main() -> None:
    config = get_config()
    init_database(config.database_path)
    connection = get_connection(config.database_path)
    try:
        repository = CustomerRepository(connection)
        sync_service = SyncService(GoogleSheetsClient(config), repository)
        result = sync_service.sync()
    finally:
        connection.close()

    print(
        "Sync completed. "
        f"Fetched={result.fetched_count}, "
        f"Inserted={result.inserted_count}, "
        f"Skipped={result.skipped_count}, "
        f"Deleted={result.deleted_count}"
    )


if __name__ == "__main__":
    main()

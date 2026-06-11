from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH if ENV_PATH.exists() else None)


@dataclass(frozen=True)
class AppConfig:
    app_name: str = os.getenv("APP_NAME", "Personal CRM")
    database_path: Path = Path(os.getenv("DATABASE_PATH", BASE_DIR / "data" / "crm.sqlite3"))
    google_service_account_file: Path = Path(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", BASE_DIR / "credentials" / "service_account.json")
    )
    google_sheet_id: str = os.getenv("GOOGLE_SHEET_ID", "")
    google_worksheet_name: str = os.getenv("GOOGLE_WORKSHEET_NAME", "formresponse_1")
    timestamp_column: str = os.getenv("GOOGLE_TIMESTAMP_COLUMN", "時間戳記")
    name_column: str = os.getenv("GOOGLE_NAME_COLUMN", "暱稱")
    email_column: str = os.getenv("GOOGLE_EMAIL_COLUMN", "電子郵件地址")
    message_column: str = os.getenv("GOOGLE_MESSAGE_COLUMN", "補充資訊")
    contact_method_column: str = os.getenv("GOOGLE_CONTACT_METHOD_COLUMN", "聯絡方式")
    location_column: str = os.getenv("GOOGLE_LOCATION_COLUMN", "居住地區")
    form_submission_id_column: str = os.getenv("GOOGLE_FORM_SUBMISSION_ID_COLUMN", "")
    default_status: str = os.getenv("DEFAULT_STATUS", "Open")


def get_config() -> AppConfig:
    config = AppConfig()
    config.database_path.parent.mkdir(parents=True, exist_ok=True)
    return config


def normalize_google_sheet_id(sheet_value: str) -> str:
    raw_value = (sheet_value or "").strip()
    if not raw_value:
        return ""

    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", raw_value)
    if match:
        return match.group(1)

    return raw_value

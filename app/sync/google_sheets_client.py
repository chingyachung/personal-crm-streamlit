from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound

from app.config import AppConfig, normalize_google_sheet_id
from app.models.customer import Customer


class GoogleSheetsClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def fetch_customers(self) -> list[Customer]:
        records = self._get_records()
        customers: list[Customer] = []

        for row in records:
            timestamp = str(row.get(self.config.timestamp_column, "")).strip()
            name = self._extract_name(row)
            email = str(row.get(self.config.email_column, "")).strip()
            message = self._build_message(row)
            raw_json = json.dumps(row, ensure_ascii=False)
            raw_text = self._build_raw_text(row)

            if not name and not email and not raw_text:
                continue

            form_submission_id = self._extract_submission_id(row, timestamp, name, email, message)
            customers.append(
                Customer(
                    id=None,
                    form_submission_id=form_submission_id,
                    timestamp=timestamp,
                    name=name or "Unknown",
                    email=email or "Unknown",
                    message=message,
                    raw_json=raw_json,
                    raw_text=raw_text,
                    notes="",
                    status=self.config.default_status,
                    tags="",
                )
            )

        return customers

    def _get_records(self) -> list[dict[str, Any]]:
        normalized_sheet_id = normalize_google_sheet_id(self.config.google_sheet_id)
        if not normalized_sheet_id:
            raise ValueError("GOOGLE_SHEET_ID is not configured.")

        service_account_file = Path(self.config.google_service_account_file)
        if not service_account_file.exists():
            raise FileNotFoundError(
                f"Google service account file not found: {service_account_file}"
            )

        client = gspread.service_account(filename=str(service_account_file))

        try:
            spreadsheet = client.open_by_key(normalized_sheet_id)
            worksheet = spreadsheet.worksheet(self.config.google_worksheet_name)
        except SpreadsheetNotFound as exc:
            raise ValueError("Google Sheet not found. Check GOOGLE_SHEET_ID and sharing permissions.") from exc
        except WorksheetNotFound as exc:
            raise ValueError("Worksheet not found. Check GOOGLE_WORKSHEET_NAME.") from exc

        return worksheet.get_all_records()

    def _extract_submission_id(
        self,
        row: dict[str, Any],
        timestamp: str,
        name: str,
        email: str,
        message: str,
    ) -> str:
        if self.config.form_submission_id_column:
            raw_value = str(row.get(self.config.form_submission_id_column, "")).strip()
            if raw_value:
                return raw_value

        stable_payload = "|".join([timestamp, name, email, message])
        return hashlib.sha256(stable_payload.encode("utf-8")).hexdigest()

    def _extract_name(self, row: dict[str, Any]) -> str:
        preferred_columns = [
            self.config.name_column,
            "私訊暱稱",
            "暱稱",
        ]
        for column_name in preferred_columns:
            value = str(row.get(column_name, "")).strip()
            if value:
                return value
        return ""

    def _build_message(self, row: dict[str, Any]) -> str:
        parts: list[str] = []

        contact_method = str(row.get(self.config.contact_method_column, "")).strip()
        location = str(row.get(self.config.location_column, "")).strip()

        if contact_method:
            parts.append(f"聯絡方式：{contact_method}")

        if location:
            parts.append(f"居住地區：{location}")

        if parts:
            return "\n".join(parts)

        return ""

    @staticmethod
    def _build_raw_text(row: dict[str, Any]) -> str:
        lines: list[str] = []
        for key, value in row.items():
            normalized_value = str(value).strip()
            if not normalized_value:
                continue
            lines.append(f"{key}: {normalized_value}")
        return "\n".join(lines)

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Customer:
    id: Optional[int]
    form_submission_id: str
    timestamp: str
    name: str
    email: str
    message: str
    raw_json: str
    raw_text: str
    notes: str
    status: str
    tags: str
    follow_up_date: str = ""
    last_contact_date: str = ""
    appointment_at: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ContactHistoryEntry:
    id: Optional[int]
    customer_id: int
    contact_date: str
    note: str
    created_at: Optional[str] = None

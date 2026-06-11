from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ActivityHistoryEntry:
    id: Optional[int]
    customer_id: int
    activity_type: str
    activity_datetime: str
    title: str
    note: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

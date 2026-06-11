from __future__ import annotations

import json
from datetime import date, datetime
from html import escape
from pathlib import Path
import streamlit as st

from app.models.activity_history import ActivityHistoryEntry
from app.models.contact_history import ContactHistoryEntry
from app.models.customer import Customer


THEME_PATH = Path(__file__).resolve().parent / "theme.css"


def inject_styles() -> None:
    theme_css = THEME_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{theme_css}</style>", unsafe_allow_html=True)


def render_customer_card(customer: Customer) -> None:
    summary = format_customer_summary(customer) or "No summary available."
    tag_badges = [_render_tag_badge(tag) for tag in customer.tags.split(",") if tag.strip()]
    if not tag_badges:
        tag_badges = ['<span class="crm-badge crm-tag-none">No Tags</span>']

    due_badge = (
        '<span class="crm-badge crm-followup-due">⚠️ Follow-up Due</span>'
        if is_follow_up_due(customer.follow_up_date)
        else ""
    )

    follow_up_line = (
        f'<div class="crm-detail-line">Next Follow-up: {escape(customer.follow_up_date)}</div>'
        if customer.follow_up_date
        else ""
    )
    last_contact_line = (
        f'<div class="crm-detail-line">Last Contact: {escape(customer.last_contact_date)}</div>'
        if customer.last_contact_date
        else ""
    )
    card_markup = (
        f'<div class="crm-card crm-card-interactive">'
        f'<div class="crm-card-click-anchor"></div>'
        f'<div class="crm-name">{escape(customer.name)}</div>'
        f'<div class="crm-email">{escape(customer.email)}</div>'
        f'<div class="crm-message">{escape(summary)}</div>'
        f"{follow_up_line}"
        f"{last_contact_line}"
        f'<div class="crm-badge-label">Status</div>'
        f'<div class="crm-detail-line"><span class="crm-badge {_status_class(customer.status)}">{escape(customer.status)}</span> {due_badge}</div>'
        f'<div class="crm-badge-label" style="margin-top: 0.6rem;">Tags</div>'
        f'<div class="crm-detail-line">{" ".join(tag_badges)}</div>'
        f"</div>"
    )

    with st.container():
        st.markdown(card_markup, unsafe_allow_html=True)
        st.button(
            f"Open {customer.name}",
            key=f"customer-card-select-{customer.id}",
            on_click=_select_customer,
            args=(customer.id,),
        )


def format_customer_summary(customer: Customer) -> str:
    row = _parse_raw_json(customer.raw_json)
    contact_method = _get_first_value(row, ["聯絡方式", "聯絡方式（Line ID / Telegram / 手機）"])
    location = _get_first_value(row, ["居住地區", "你現在居住的地區", "你現在居住的地區（縣市即可）"])

    lines: list[str] = []
    if contact_method:
        lines.append(f"聯絡方式：{contact_method}")
    if location:
        lines.append(f"居住地區：{location}")

    return "\n".join(lines)


def render_dashboard_stats(stats: dict[str, int]) -> None:
    stat_items = [
        ("Total Customers", stats.get("total_customers", 0)),
        ("Open Customers", stats.get("open_customers", 0)),
        ("VIP Customers", stats.get("vip_customers", 0)),
        ("Hot Leads", stats.get("hot_leads", 0)),
        ("New This Week", stats.get("new_this_week", 0)),
    ]
    columns = st.columns(len(stat_items), gap="small")
    for column, (label, value) in zip(columns, stat_items):
        with column:
            st.markdown(
                f"""
                <div class="crm-stat-card">
                    <div class="crm-stat-label">{label}</div>
                    <div class="crm-stat-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_appointment_list(title: str, customers: list[Customer], *, empty_message: str) -> None:
    st.markdown(f"**{title}**")
    if not customers:
        st.info(empty_message)
        return

    is_today = title == "Today's Appointments"
    for customer in customers:
        appointment_line = format_appointment_line(customer.appointment_at, is_today, customer.name)
        note_line = customer.email
        st.markdown(
            f"""
            <div class="crm-history-item">
                <div class="crm-history-date">{escape(appointment_line)}</div>
                <div class="crm-history-note">{escape(note_line)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_contact_history(entries: list[ContactHistoryEntry]) -> int | None:
    if not entries:
        st.info("No contact history yet.")
        return None

    for entry in entries:
        history_col, action_col = st.columns([8, 1], gap="small")
        with history_col:
            st.markdown(
                f"""
                <div class="crm-history-item">
                    <div class="crm-history-date">{entry.contact_date}</div>
                    <div class="crm-history-note">{entry.note}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with action_col:
            if st.button("Delete", key=f"delete-history-{entry.id}", use_container_width=True):
                return entry.id

    return None


def render_activity_history(entries: list[ActivityHistoryEntry]) -> None:
    if not entries:
        st.info("No activity history yet.")
        return

    for entry in entries:
        title_line = (
            f'<div class="crm-history-note">Title: {escape(entry.title)}</div>'
            if entry.title
            else ""
        )
        note_line = (
            f'<div class="crm-history-note">{escape(entry.note)}</div>'
            if entry.note
            else ""
        )
        st.markdown(
            f"""
            <div class="crm-history-item">
                <div class="crm-history-date">{escape(format_activity_datetime(entry.activity_datetime))}</div>
                <div class="crm-history-type">{escape(format_activity_type(entry.activity_type))}</div>
                {title_line}
                {note_line}
            </div>
            """,
            unsafe_allow_html=True,
        )


def _status_class(status: str) -> str:
    normalized = status.strip().lower().replace(" ", "-")
    if normalized in {"open", "in-progress", "closed"}:
        return f"crm-status-{normalized}"
    return "crm-status-open"


def _render_tag_badge(tag: str) -> str:
    normalized = tag.strip().lower().replace(" ", "-")
    if normalized in {"follow-up", "followup"}:
        css_class = "crm-tag-follow-up"
    elif normalized == "vip":
        css_class = "crm-tag-vip"
    elif normalized in {"hot-lead", "hotlead"}:
        css_class = "crm-tag-hot-lead"
    else:
        css_class = "crm-tag-default"
    return f'<span class="crm-badge {css_class}">{tag.strip()}</span>'


def _parse_raw_json(raw_json: str) -> dict[str, str]:
    if not raw_json:
        return {}
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value).strip() for key, value in parsed.items()}


def _get_first_value(row: dict[str, str], candidates: list[str]) -> str:
    for key in candidates:
        value = row.get(key, "").strip()
        if value:
            return value
    return ""


def is_follow_up_due(follow_up_date: str) -> bool:
    if not follow_up_date:
        return False
    try:
        return date.fromisoformat(follow_up_date) <= date.today()
    except ValueError:
        return False


def format_appointment_line(raw_value: str, is_today: bool, customer_name: str) -> str:
    parsed = _parse_datetime(raw_value)
    if not parsed:
        return "No appointment date"
    if is_today:
        return f"{parsed.strftime('%H:%M')} {customer_name}"
    return f"{parsed.strftime('%Y-%m-%d %H:%M')} - {customer_name}"


def format_appointment_datetime(raw_value: str) -> str:
    parsed = _parse_datetime(raw_value)
    if not parsed:
        return raw_value
    return parsed.strftime("%Y-%m-%d %H:%M")


def format_activity_datetime(raw_value: str) -> str:
    parsed = _parse_datetime(raw_value)
    if not parsed:
        return raw_value
    if parsed.time() == datetime.min.time():
        return parsed.strftime("%Y-%m-%d")
    return parsed.strftime("%Y-%m-%d %H:%M")


def format_activity_type(activity_type: str) -> str:
    labels = {
        "contact": "Contact",
        "follow_up": "Follow-up",
        "appointment": "Appointment",
    }
    return labels.get(activity_type, activity_type.replace("_", " ").title())




def _parse_datetime(raw_value: str) -> datetime | None:
    if not raw_value:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw_value, fmt)
        except ValueError:
            continue
    return None


def _select_customer(customer_id: int) -> None:
    st.session_state.selected_customer_id = customer_id

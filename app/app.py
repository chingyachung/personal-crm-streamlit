from __future__ import annotations

from datetime import date, datetime, time
from html import escape
import traceback
from contextlib import contextmanager

import streamlit as st

from app.config import get_config
from app.database.connection import get_connection
from app.database.init_db import init_database
from app.dashboard.components import (
    format_appointment_datetime,
    format_customer_summary,
    inject_styles,
    is_follow_up_due,
    render_appointment_list,
    render_contact_history,
    render_customer_card,
    render_dashboard_stats,
)
from app.repositories.customer_repository import CustomerRepository
from app.services.customer_service import CustomerService
from app.sync.google_sheets_client import GoogleSheetsClient
from app.sync.sync_service import SyncService


config = get_config()
init_database(config.database_path)


@contextmanager
def get_repository() -> CustomerRepository:
    connection = get_connection(config.database_path)
    try:
        yield CustomerRepository(connection)
    finally:
        connection.close()


def build_customer_service() -> CustomerService:
    with get_repository() as repository:
        return CustomerService(repository)


def run_sync() -> tuple[bool, str, str]:
    try:
        with get_repository() as repository:
            sync_service = SyncService(GoogleSheetsClient(config), repository)
            result = sync_service.sync()
        message = (
            f"Sync completed. Fetched {result.fetched_count} rows, "
            f"inserted {result.inserted_count}, skipped {result.skipped_count} existing records, "
            f"deleted {result.deleted_count} removed records."
        )
        return True, message, ""
    except Exception as exc:  # pragma: no cover
        summary = f"{type(exc).__name__}: {exc}"
        details = traceback.format_exc()
        return False, summary, details


def main() -> None:
    st.set_page_config(
        page_title=config.app_name,
        page_icon="📇",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_styles()

    st.title(config.app_name)
    st.caption("Google Sheets -> SQLite -> Streamlit")

    if "selected_customer_id" not in st.session_state:
        st.session_state.selected_customer_id = None

    with st.sidebar:
        st.subheader("Sync")
        if st.button("Sync from Google Sheet", use_container_width=True):
            ok, message, details = run_sync()
            if ok:
                st.success(message)
            else:
                st.error(message)
                with st.expander("Show error details"):
                    st.code(details)

        st.divider()
        st.subheader("Search & Filters")
        search_text = st.text_input("Search", placeholder="Name, email, or message")
        status_filter = st.selectbox("Status", options=[""] + CustomerService.STATUS_OPTIONS, format_func=lambda x: x or "All")

        with get_repository() as repository:
            tag_options = CustomerService(repository).get_available_tags()
        tag_filter = st.selectbox("Tags", options=[""] + tag_options, format_func=lambda x: x or "All")

    with get_repository() as repository:
        customer_service = CustomerService(repository)
        customers = customer_service.search_customers(
            search=search_text,
            status=status_filter,
            tag=tag_filter,
        )
        dashboard_stats = customer_service.get_dashboard_stats()
        todays_appointments = customer_service.get_todays_appointments()
        upcoming_appointments = customer_service.get_upcoming_appointments()

    render_dashboard_stats(dashboard_stats)
    st.markdown("<div style='height: 1.25rem;'></div>", unsafe_allow_html=True)

    appointments_col, upcoming_col = st.columns(2, gap="large")
    with appointments_col:
        render_appointment_list(
            "Today's Appointments",
            todays_appointments,
            empty_message="No appointments scheduled for today.",
        )
    with upcoming_col:
        render_appointment_list(
            "Upcoming Appointments",
            upcoming_appointments,
            empty_message="No upcoming appointments scheduled.",
        )

    st.markdown("<div style='height: 1.25rem;'></div>", unsafe_allow_html=True)

    left_col, right_col = st.columns([1.1, 1], gap="large")

    with left_col:
        st.subheader("Customers")
        if not customers:
            st.info("No customers found. Run a sync or adjust the filters.")

        for customer in customers:
            render_customer_card(customer)

    with right_col:
        st.subheader("Customer Detail")
        selected_id = st.session_state.selected_customer_id
        if not selected_id and customers:
            selected_id = customers[0].id
            st.session_state.selected_customer_id = selected_id

        if not selected_id:
            st.info("Select a customer to view details.")
            return

        with get_repository() as repository:
            customer_service = CustomerService(repository)
            customer = customer_service.get_customer(selected_id)

        if not customer:
            st.warning("Customer not found.")
            return

        st.markdown(f"### {customer.name}")
        st.write(customer.email)
        st.caption(f"Submitted at: {customer.timestamp or 'Unknown'}")
        st.markdown("**CRM Summary**")
        st.write(format_customer_summary(customer) or "No summary available.")
        if customer.follow_up_date:
            if _render_summary_remove_row(
                customer.id,
                label="Next Follow-up",
                value=customer.follow_up_date,
                button_key=f"remove-follow-up-detail-{customer.id}",
                help_text="Remove next follow-up date",
            ):
                _remove_summary_field(
                    customer=customer,
                    field_name="follow_up_date",
                    success_message="Follow-up removed.",
                )
        if customer.last_contact_date:
            if _render_summary_remove_row(
                customer.id,
                label="Last Contact",
                value=customer.last_contact_date,
                button_key=f"remove-last-contact-detail-{customer.id}",
                help_text="Remove last contact date",
            ):
                _remove_summary_field(
                    customer=customer,
                    field_name="last_contact_date",
                    success_message="Last contact removed.",
                )
        if customer.appointment_at:
            if _render_summary_remove_row(
                customer.id,
                label="Appointment",
                value=format_appointment_datetime(customer.appointment_at),
                button_key=f"remove-appointment-detail-{customer.id}",
                help_text="Remove appointment",
            ):
                _remove_summary_field(
                    customer=customer,
                    field_name="appointment_at",
                    success_message="Appointment removed.",
                )
        if is_follow_up_due(customer.follow_up_date):
            st.warning("⚠️ Follow-up Due")

        with st.expander("View Full Original Form Content"):
            raw_content = customer.raw_text or "No original form content available."
            formatted_raw_content = escape(raw_content).replace("\n", "<br>")
            st.markdown(
                f'<div class="original-form-content">{formatted_raw_content}</div>',
                unsafe_allow_html=True,
            )

        notes = st.text_area("Notes", value=customer.notes, height=180, key=f"notes-{customer.id}")
        status = st.selectbox(
            "Status",
            options=CustomerService.STATUS_OPTIONS,
            index=CustomerService.STATUS_OPTIONS.index(customer.status)
            if customer.status in CustomerService.STATUS_OPTIONS
            else 0,
            key=f"status-{customer.id}",
        )
        tags = st.text_input(
            "Tags",
            value=customer.tags,
            placeholder="VIP, Follow-up, Hot lead",
            key=f"tags-{customer.id}",
        )

        _initialize_date_state(customer.id, "follow_up_date", _parse_iso_date(customer.follow_up_date))
        with st.container():
            follow_up_date = st.date_input(
                "Next Follow-up Date",
                value=_parse_iso_date(customer.follow_up_date),
                format="YYYY-MM-DD",
                key=f"follow-up-date-{customer.id}",
                on_change=_handle_date_widget_change,
                args=(customer.id, "follow_up_date", f"follow-up-date-{customer.id}"),
            )

        _initialize_date_state(customer.id, "last_contact_date", _parse_iso_date(customer.last_contact_date))
        with st.container():
            last_contact_date = st.date_input(
                "Last Contact Date",
                value=_parse_iso_date(customer.last_contact_date),
                format="YYYY-MM-DD",
                key=f"last-contact-date-{customer.id}",
                on_change=_handle_date_widget_change,
                args=(customer.id, "last_contact_date", f"last-contact-date-{customer.id}"),
            )

        appointment_date_value, appointment_time_value = _parse_appointment_datetime(customer.appointment_at)
        _initialize_date_state(customer.id, "appointment_date", appointment_date_value)
        with st.container():
            appointment_date_col, appointment_time_col = st.columns([3, 2], gap="small")
            with appointment_date_col:
                appointment_date = st.date_input(
                    "Appointment",
                    value=appointment_date_value,
                    format="YYYY-MM-DD",
                    key=f"appointment-date-{customer.id}",
                    on_change=_handle_date_widget_change,
                    args=(customer.id, "appointment_date", f"appointment-date-{customer.id}"),
                )
            with appointment_time_col:
                appointment_time = st.time_input(
                    "Time",
                    value=appointment_time_value,
                    step=1800,
                    key=f"appointment-time-{customer.id}",
                )

        if st.button("Save", key=f"save-customer-{customer.id}"):
            next_follow_up_value = _get_effective_date_for_save(
                customer.id,
                "follow_up_date",
                follow_up_date,
            )
            next_last_contact_value = _get_effective_date_for_save(
                customer.id,
                "last_contact_date",
                last_contact_date,
            )
            next_appointment_value = _get_effective_appointment_for_save(
                customer.id,
                appointment_date,
                appointment_time,
            )
            with get_repository() as repository:
                service = CustomerService(repository)
                service.update_internal_fields(
                    customer.id,
                    notes=notes,
                    status=status,
                    tags=tags,
                    follow_up_date=next_follow_up_value,
                    last_contact_date=next_last_contact_value,
                    appointment_at=next_appointment_value,
                )
            st.success("Customer updated and saved to SQLite.")
            st.rerun()

        st.markdown("**Contact History**")
        with get_repository() as repository:
            history_service = CustomerService(repository)
            history_entries = history_service.list_contact_history(customer.id)
        deleted_history_id = render_contact_history(history_entries)
        if deleted_history_id is not None:
            with get_repository() as repository:
                CustomerService(repository).delete_contact_history(deleted_history_id)
            st.success("Contact history deleted.")
            st.rerun()

        with st.form(f"contact-history-{customer.id}"):
            history_date = st.date_input(
                "Interaction Date",
                value=date.today(),
                format="YYYY-MM-DD",
                key=f"history-date-{customer.id}",
            )
            history_note = st.text_area(
                "Interaction Note",
                placeholder="Customer replied on LINE",
                key=f"history-note-{customer.id}",
            )
            history_submitted = st.form_submit_button("Add Contact History")

            if history_submitted:
                with get_repository() as repository:
                    CustomerService(repository).add_contact_history(
                        customer.id,
                        contact_date=_serialize_date(history_date),
                        note=history_note,
                    )
                st.success("Contact history added.")
                st.rerun()

        st.caption(f"Created at: {customer.created_at} | Updated at: {customer.updated_at}")


def _parse_iso_date(raw_value: str) -> date | None:
    if not raw_value:
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError:
        return None


def _serialize_date(value: date | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


def _parse_appointment_datetime(raw_value: str) -> tuple[date | None, time]:
    if not raw_value:
        return None, _default_appointment_time()

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(raw_value, fmt)
            return parsed.date(), parsed.time().replace(second=0, microsecond=0)
        except ValueError:
            continue

    parsed_date = _parse_iso_date(raw_value)
    if parsed_date:
        return parsed_date, _default_appointment_time()
    return None, _default_appointment_time()


def _combine_date_and_time(value_date: date | None, value_time: time | None) -> str:
    if value_date is None:
        return ""
    actual_time = value_time or _default_appointment_time()
    return f"{value_date.isoformat()} {actual_time.strftime('%H:%M:%S')}"


def _default_appointment_time() -> time:
    return time(hour=9, minute=0)


def _get_effective_appointment_for_save(customer_id: int, value_date: date | None, value_time: time | None) -> str:
    if st.session_state.get(f"appointment_date-cleared-{customer_id}", False):
        return ""
    return _combine_date_and_time(value_date, value_time)


def _initialize_date_state(customer_id: int, field_name: str, db_value: date | None) -> None:
    cleared_key = f"{field_name}-cleared-{customer_id}"
    if cleared_key not in st.session_state:
        st.session_state[cleared_key] = db_value is None


def _handle_date_widget_change(customer_id: int, field_name: str, widget_key: str) -> None:
    widget_value = st.session_state.get(widget_key)
    normalized_value = _normalize_widget_date(widget_value)
    cleared_key = f"{field_name}-cleared-{customer_id}"
    st.session_state[cleared_key] = normalized_value == ""


def _get_effective_date_for_save(customer_id: int, field_name: str, fallback_value: date | None) -> str:
    widget_key = _date_widget_key(customer_id, field_name)
    widget_value = st.session_state.get(widget_key, fallback_value)
    normalized_value = _normalize_widget_date(widget_value)
    if st.session_state.get(f"{field_name}-cleared-{customer_id}", False):
        return ""
    return normalized_value


def _date_widget_key(customer_id: int, field_name: str) -> str:
    if field_name == "follow_up_date":
        return f"follow-up-date-{customer_id}"
    if field_name == "last_contact_date":
        return f"last-contact-date-{customer_id}"
    if field_name == "appointment_date":
        return f"appointment-date-{customer_id}"
    raise ValueError(f"Unknown date field: {field_name}")


def _normalize_widget_date(value: object) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _render_summary_remove_row(
    customer_id: int,
    *,
    label: str,
    value: str,
    button_key: str,
    help_text: str,
) -> bool:
    label_col, remove_col = st.columns([5, 1], gap="small")
    with label_col:
        st.markdown(f"**{label}:** {value}")
    with remove_col:
        return st.button(
            "Remove",
            key=button_key,
            help=help_text,
            use_container_width=True,
        )


def _remove_summary_field(*, customer, field_name: str, success_message: str) -> None:
    payload = {
        "follow_up_date": customer.follow_up_date,
        "last_contact_date": customer.last_contact_date,
        "appointment_at": customer.appointment_at,
    }
    payload[field_name] = ""

    with get_repository() as repository:
        service = CustomerService(repository)
        service.update_internal_fields(
            customer.id,
            notes=customer.notes,
            status=customer.status,
            tags=customer.tags,
            follow_up_date=payload["follow_up_date"],
            last_contact_date=payload["last_contact_date"],
            appointment_at=payload["appointment_at"],
        )

    if field_name == "follow_up_date":
        st.session_state[f"follow-up-date-{customer.id}"] = None
        st.session_state[f"follow_up_date-cleared-{customer.id}"] = True
    elif field_name == "last_contact_date":
        st.session_state[f"last-contact-date-{customer.id}"] = None
        st.session_state[f"last_contact_date-cleared-{customer.id}"] = True
    elif field_name == "appointment_at":
        st.session_state[f"appointment-date-{customer.id}"] = None
        st.session_state[f"appointment-time-{customer.id}"] = _default_appointment_time()
        st.session_state[f"appointment_date-cleared-{customer.id}"] = True

    st.success(success_message)
    st.rerun()


if __name__ == "__main__":
    main()

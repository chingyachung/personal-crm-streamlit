# Personal CRM

Personal CRM is a local-first customer management system built for solo operators and small teams who collect leads through Google Forms and want a lightweight internal dashboard without deploying a web app. It syncs Google Sheets data into a local SQLite database, then uses Streamlit to provide a searchable CRM for notes, follow-ups, appointments, and day-to-day customer management.

The project is designed to be practical, maintainable, and easy to extend. Google Sheets remains the external source of form submissions, while SQLite becomes the primary local database for querying, editing, and preserving internal CRM data over time.

## Features

- Sync customer submissions from Google Sheets into a local SQLite database
- Preserve internal CRM fields separately from the source form data
- Search customers by name, email, message, and raw synced content
- Filter by status and tags
- Manage notes, follow-up dates, last contact dates, and appointments
- Track contact history and backend activity history
- Show upcoming and same-day appointments in the dashboard
- Remove customers automatically when their row is deleted from Google Sheets
- Run entirely on a local machine with no cloud deployment required

## Tech Stack

- Python
- Streamlit
- SQLite
- Google Sheets API
- Google Forms

## System Architecture

```text
Google Form
    ↓
Google Sheets
    ↓
Sync Service
    ↓
SQLite
    ↓
Streamlit Dashboard
```

Google Forms and Google Sheets are used only as the external intake layer. After synchronization, the application works primarily against SQLite, which acts as the durable local system of record for CRM operations such as searching, filtering, note-taking, scheduling, and status updates.

This local-first approach makes the app simple to run, resilient to browser restarts, and suitable for long-term use without relying on direct Google Sheets reads for every interaction.

## Project Structure

```text
app/
├── dashboard/      # Streamlit UI components and shared styling
├── database/       # SQLite schema, connection helpers, and migrations
├── models/         # Domain models used across the application
├── repositories/   # Persistence layer and SQL access
├── services/       # Business logic and orchestration
├── sync/           # Google Sheets synchronization logic
├── app.py          # Main Streamlit application
└── config.py       # Environment-driven configuration

tests/              # Automated tests
streamlit_app.py    # Launch entry point
requirements.txt    # Python dependencies
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/personal-crm-streamlit.git
cd personal-crm-streamlit
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your local environment file

```bash
cp .env.example .env
```

## Configuration

The application reads configuration from `.env`.

### Required environment variables

| Variable | Description |
| --- | --- |
| `APP_NAME` | Display name shown in the Streamlit app |
| `DATABASE_PATH` | Path to the local SQLite database |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to the Google service account JSON file |
| `GOOGLE_SHEET_ID` | Google Sheet ID or full Google Sheets URL |
| `GOOGLE_WORKSHEET_NAME` | Worksheet tab name inside the spreadsheet |
| `GOOGLE_TIMESTAMP_COLUMN` | Column name for submission timestamp |
| `GOOGLE_NAME_COLUMN` | Column name mapped to customer name |
| `GOOGLE_EMAIL_COLUMN` | Column name mapped to customer email |
| `GOOGLE_MESSAGE_COLUMN` | Column name used as the primary message/summary field |
| `GOOGLE_CONTACT_METHOD_COLUMN` | Column used for the CRM summary contact method |
| `GOOGLE_LOCATION_COLUMN` | Column used for the CRM summary location |
| `GOOGLE_FORM_SUBMISSION_ID_COLUMN` | Optional unique submission ID column |
| `DEFAULT_STATUS` | Default CRM status for new customers |

### Google Service Account setup

1. Create a Google Cloud project
2. Enable the Google Sheets API
3. Create a service account
4. Download the service account JSON key
5. Place the file at the path configured in `GOOGLE_SERVICE_ACCOUNT_FILE`
6. Share the target Google Sheet with the service account email

By default, the project expects:

```text
./credentials/service_account.json
```

## Usage

### Run a one-time sync from the command line

```bash
python -m app.sync.run_sync
```

### Launch the CRM dashboard

```bash
streamlit run streamlit_app.py
```

Once the dashboard is running:

1. Click **Sync from Google Sheet**
2. Review newly imported customers
3. Search, filter, and update CRM fields locally

The app runs locally by default at:

```text
http://localhost:8501
```

## Database Design

The primary table is `customers`, which stores both synced submission data and internal CRM fields.

### Customers table

| Field | Purpose |
| --- | --- |
| `id` | Local primary key |
| `form_submission_id` | Stable external submission identifier |
| `timestamp` | Original form submission time |
| `name` | Customer name |
| `email` | Customer email |
| `message` | Primary summary/message field derived from the form |
| `raw_json` | Full original row payload as JSON |
| `raw_text` | Full original row payload as plain text for search/AI use cases |
| `notes` | Internal notes maintained in the CRM |
| `status` | Current CRM status |
| `tags` | Internal tags for segmentation and follow-up |
| `follow_up_date` | Current next follow-up date |
| `last_contact_date` | Current last contact date |
| `appointment_at` | Current appointment datetime |
| `created_at` | Local record creation timestamp |
| `updated_at` | Local record update timestamp |

### Contact history

The `contact_history` table stores user-entered interaction notes tied to a customer.

### Activity history

The `activity_history` table stores backend audit records for contact, follow-up, and appointment changes. It is intended for future reporting and historical analytics while the current UI remains focused on the latest CRM state.

## Synchronization Logic

### Initial synchronization

On the first sync, the application reads all rows from the configured Google Sheet, transforms them into customer records, and writes them into SQLite.

### Incremental synchronization

On later syncs, the application only inserts new form submissions and keeps existing local CRM edits intact.

### Preservation of local fields

The following fields are managed locally and are not overwritten during sync:

- `notes`
- `status`
- `tags`

This allows the Google Form / Google Sheets pipeline to remain a clean intake source while the CRM stores internal operational data independently.

### Automatic deletion

Customer records are managed by Google Sheets. To remove a customer, delete the corresponding row in Google Sheets. The CRM will reflect the change automatically after data synchronization.

## Design Highlights

### Local-first architecture

The system is intentionally local-first. Google Sheets is used for intake, but SQLite is the working database for everything the user does inside the CRM. This keeps the app fast, persistent, and easy to back up.

### Repository Pattern

Database access is isolated in the repository layer, making SQL easier to maintain and future storage migrations more predictable.

### Service Layer

Business rules live in services rather than in Streamlit pages. This keeps UI code lighter and makes features such as scheduling, synchronization, and historical tracking easier to test.

### Clear separation of concerns

- `sync/` handles external data ingestion
- `repositories/` handles persistence
- `services/` handles business logic
- `dashboard/` handles presentation

That separation keeps the project practical today while leaving room for future growth.

## Future Improvements

- PostgreSQL support for multi-user or hosted deployments
- Authentication and role-based access control
- AI and RAG features over customer notes, form messages, and history
- Analytics dashboards powered by activity history
- Richer reporting around appointments, follow-ups, and engagement trends

## License

This project is released under the MIT License.

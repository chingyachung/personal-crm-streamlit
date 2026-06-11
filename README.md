# Personal CRM / Customer Management System

這是一個本地執行的 Personal CRM，使用 `Python + SQLite + Streamlit`，並透過 Google Sheet 作為表單資料來源。

系統流程如下：

```text
Google Form
    ↓
Google Sheet
    ↓
Sync Service
    ↓
SQLite
    ↓
Streamlit Dashboard
```

重點是：Google Sheet 只作為外部來源，日常查詢與編輯一律走本地 SQLite，因此 `Notes / Status / Tags` 在關閉 Streamlit、重開電腦後仍會永久保留。

> Customer records are managed by Google Sheets. To remove a customer, delete the corresponding row in Google Sheets. The CRM will reflect the change automatically after data synchronization.

## 功能

- 首次同步 Google Sheet 全部資料到 SQLite
- 後續增量同步，只新增新的 form submission
- 已存在資料不覆蓋 `notes`
- 已存在資料不覆蓋 `status`
- 已存在資料不覆蓋 `tags`
- Streamlit CRM 介面
- 搜尋 `Name / Email / Message`
- 依 `Status / Tags` 篩選
- 客戶詳細頁與內部欄位編輯

## 專案結構

```text
app/
├── dashboard/      # Streamlit UI 元件與樣式
├── database/       # SQLite 連線、schema、初始化
├── models/         # Domain models
├── repositories/   # Repository pattern，封裝資料存取
├── services/       # 業務邏輯，例如 customer update
├── sync/           # Google Sheets 同步邏輯
├── app.py          # Streamlit 入口
└── config.py       # 環境設定與路徑
```

## 安裝

### 1. 建立虛擬環境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安裝依賴

```bash
pip install -r requirements.txt
```

### 3. 設定環境變數

```bash
cp .env.example .env
```

編輯 `.env`：

- `GOOGLE_SHEET_ID`: 你的 Google Sheet ID
- `GOOGLE_WORKSHEET_NAME`: worksheet 名稱，例如 `formresponse_1`
- `GOOGLE_*_COLUMN`: 對應 Google Sheet 欄位名稱
- `GOOGLE_CONTACT_METHOD_COLUMN`: CRM Summary 內顯示的聯絡方式欄位
- `GOOGLE_LOCATION_COLUMN`: CRM Summary 內顯示的居住地區欄位
- `GOOGLE_FORM_SUBMISSION_ID_COLUMN`: 如果 Sheet 內有唯一提交 ID，請填該欄位名稱；若留空，系統會用 `timestamp + name + email + message` 產生穩定雜湊 ID

### 4. 準備 Google Service Account

把 service account JSON 放到：

```text
./credentials/service_account.json
```

並且：

1. 到 Google Cloud 建立 Service Account
2. 啟用 Google Sheets API
3. 下載 JSON key
4. 用該 service account email 分享你的 Google Sheet 讀取權限

## 執行

```bash
streamlit run streamlit_app.py
```

啟動後：

1. 先按左側 `Sync from Google Sheet`
2. 系統會建立 SQLite 檔案到 `DATABASE_PATH`
3. 之後 Dashboard 從 SQLite 讀資料，不會每次重新直連 Google Sheet

如果你想先在命令列手動同步一次，也可以執行：

```bash
python -m app.sync.run_sync
```

補充：

- `GOOGLE_SHEET_ID` 可以填純 ID，也可以直接貼整段 Google Sheet 網址
- `GOOGLE_WORKSHEET_NAME` 要和工作表分頁名稱完全一致，例如你的 `formresponse_1`
- 這個版本會同時保存 `raw_json` 和 `raw_text`，方便未來做 RAG

## SQLite Schema

`customers` table:

```sql
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    form_submission_id TEXT NOT NULL UNIQUE,
    timestamp TEXT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    message TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '',
    raw_text TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Open',
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## 同步邏輯

### First Sync

- 讀取 Google Sheet 所有 rows
- 轉成 customer records
- 寫入 SQLite

### Incremental Sync

- 以 `form_submission_id` 判斷是否已存在
- 若已存在：略過，不覆蓋內部欄位
- 若不存在：新增到 SQLite
- 若 Google Sheets 中的 row 已刪除：下次同步時會自動從 CRM 移除對應 customer

這表示以下欄位會永久保留在本地資料庫：

- `notes`
- `status`
- `tags`

另外，每一筆表單也會額外保存：

- `raw_json`: 原始 Google Sheet row JSON
- `raw_text`: 適合未來餵給 LLM / RAG 的純文字版本

## 設計說明

### Repository Pattern

- `repositories/customer_repository.py` 專責 SQL 與持久層
- 未來若從 SQLite 改成 PostgreSQL，可新增另一個 repository implementation，而不是重寫整個 UI

### Service Layer

- `services/customer_service.py` 負責業務規則
- `sync/sync_service.py` 負責同步流程
- Streamlit 頁面只負責互動與顯示

## 未來如何擴充

### Phase 2: PostgreSQL

建議做法：

1. 保留 `CustomerService`
2. 抽象 repository 介面
3. 新增 PostgreSQL repository
4. 將 `database/connection.py` 替換成可依環境切換 SQLite / PostgreSQL

目前的分層設計已經把 SQL 與 UI 分開，後續遷移成本會低很多。

### Phase 3: Authentication

可新增：

- `users` table
- `auth_service.py`
- Streamlit login gate

由於 customer 資料操作已集中在 service/repository，加入登入不需要重寫同步與資料模型。

### Phase 4: RAG

未來可把以下欄位拿來建知識庫：

- `message`
- `notes`
- `raw_text`

可能新增模組：

```text
app/
├── rag/
│   ├── chunking.py
│   ├── embeddings.py
│   ├── vector_store.py
│   └── query_service.py
```

未來可支援：

- Summarize customer history
- Find customers mentioning AWS
- Find customers mentioning Kubernetes
- Generate follow-up recommendations

## Git Workflow

建議分支結構：

```text
main
develop
feature/*
```

開發規範：

- 不直接修改 `main`
- 所有新功能都從 `develop` 建立 `feature/*` 分支
- `feature/*` 完成後 merge 回 `develop`
- `develop` 測試完成後再 merge 到 `main`
- 每次正式發布都建立 git tag

範例：

```bash
git tag -a v1.0 -m "Initial Release"
```

## 備註

- SQLite 是唯一日常資料來源
- Streamlit 關閉後資料不會消失
- 重新開機後只要保留 `data/crm.sqlite3`，所有內部欄位都會存在
- 若想備份，只需備份 SQLite 檔案

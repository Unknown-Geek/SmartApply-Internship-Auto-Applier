# n8n Workflows

Optional n8n workflows for SmartApply automation.

> The **Telegram bot + Cerebras agent** handles applications autonomously.
> These workflows add **batch processing, monitoring, and logging** on top.

## Workflows

### 1. Identity Fetcher (`identity_fetcher.json`)
Sub-workflow that fetches user profile from Google Sheets → clean JSON.
```
Trigger → Read profileData Sheet → Transform to JSON → Output
```

### 2. Batch Applications (`batch_applications.json`) ⭐
Reads PENDING URLs from a Google Sheet and sends each to the SmartApply agent.
```
Schedule (hourly) → Read Pending Jobs → Apply via Agent → Update Sheet Status → Summary
```
**Sheet columns:** `row_id, url, company, title, status, applied_at, result`

### 3. Profile Sync (Trigger-based) (`scheduled_profile_sync.json`)
Auto-syncs profile from Google Sheets whenever a row is updated.
```
On Profile Update → Read Full Profile → Build JSON → Send to SmartApply API → Notify
```
**Endpoint:** `POST /profile/ingest`

### 4. Queue Application (`queue_application.json`)
Webook endpoint to queue forwarded Telegram links for batch processing.
```
Webhook → Prepare Row → Add to Queue Sheet → Respond OK
```
**Webhook:** `POST /webhook/smartapply-queue` with `{ "url": "https://...", "source": "Telegram Bot" }`
**Sheet columns:** `url, status, applied_at, result`

### 5. Notification Router (`notification_router.json`)
Receives webhook notifications, routes by type to Slack + Email.
```
Webhook → Route by Type (error/success/info) → Slack + Email
```
**Webhook:** `POST /webhook/smartapply-notify` with `{ "type": "error", "message": "..." }`

### 6. Application Logger (`application_logger.json`)
Logs application results to a Google Sheet tracking spreadsheet.
```
Webhook → Normalize Data → Append to Sheet → Telegram Summary (if success)
```
**Webhook:** `POST /webhook/smartapply-log` with `{ "url": "...", "status": "success", ... }`
**Sheet columns:** `timestamp, url, company, title, status, details, fields_filled, issues`

## Setup

1. **Import workflows** into n8n (Workflows → Import from File)
2. **Set n8n environment variables:**
   | Variable | Description |
   |----------|-------------|
   | `SMARTAPPLY_API_URL` | `http://localhost:8000` |
   | `TELEGRAM_BOT_TOKEN` | Your Telegram bot token |
   | `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
   | `ALERT_EMAIL` | Email for error alerts |
3. **Configure the SmartApply Server (Server `.env`):**
   - Set `SMARTAPPLY_QUEUE_WEBHOOK=https://<your-n8n>/webhook/smartapply-queue`
4. **Configure credentials:** Google Sheets OAuth2, Slack Bot (if using notifications)
5. **Create Google Sheets** with the column structures described above

# n8n Workflows

Reusable n8n sub-workflows for SmartApply.

> **Note:** The main application pipeline now runs through the **Telegram bot + Cerebras agent** directly.
> These n8n workflows serve as **optional utility modules** that can be called via the n8n API.

## Workflows

### Identity Fetcher (`identity_fetcher.json`)

Sub-workflow that fetches user profile data from Google Sheets and transforms it into clean JSON.

```
Execute Workflow Trigger → Google Sheets (Read) → Code (Transform) → Output JSON
```

**Google Sheet format** (`profileData` sheet):

| Key | Value |
|-----|-------|
| Full Name | John Doe |
| Personal Email | john@example.com |
| Mobile Number | +91 1234567890 |
| LinkedIn URL | https://linkedin.com/in/johndoe |

**Setup:**
1. Import `identity_fetcher.json` into n8n
2. Configure Google Sheets OAuth2 credentials
3. Select your spreadsheet and `profileData` sheet

## When to Use n8n

The SmartApply agent handles applications autonomously via Telegram. Use n8n workflows if you want to:

- **Batch trigger** applications from a spreadsheet
- **Schedule** periodic profile syncs
- **Chain** SmartApply with other automation tools
- **Log results** to external services (Slack, email, sheets)

To call the SmartApply API from n8n, use HTTP Request nodes pointed at `http://localhost:8000/agent/run`.

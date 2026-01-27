# n8n Workflows

This directory contains n8n workflow definitions for the SmartApply automation system.

## Workflows

### 1. Internship Application (`internship_application.json`) ⭐ Main

The **main workflow** that automates internship/job applications.

#### Workflow Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SMARTAPPLY WORKFLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐                                      │
│  │   Webhook    │ OR  │Google Sheets │                                      │
│  │   Trigger    │     │   Trigger    │                                      │
│  └──────┬───────┘     └──────┬───────┘                                      │
│         │                    │                                               │
│         └────────┬───────────┘                                               │
│                  ▼                                                           │
│  ┌───────────────────────────────────────┐                                  │
│  │ Step 1: ANALYZE                       │                                  │
│  │ HTTP → Python /agent/analyze          │                                  │
│  │ Returns: form fields, buttons         │                                  │
│  └───────────────┬───────────────────────┘                                  │
│                  │                                                           │
│                  ▼                                                           │
│  ┌───────────────────────────────────────┐                                  │
│  │ Step 2: FETCH IDENTITY                │                                  │
│  │ Execute → Identity Fetcher workflow   │                                  │
│  │ Returns: user profile from Sheets     │                                  │
│  └───────────────┬───────────────────────┘                                  │
│                  │                                                           │
│                  ▼                                                           │
│  ┌───────────────────────────────────────┐                                  │
│  │ Step 3: AI BRAIN (Gemini 2.5 Flash)   │                                  │
│  │ Input: form fields + user profile     │                                  │
│  │ Output: JSON array of browser actions │                                  │
│  └───────────────┬───────────────────────┘                                  │
│                  │                                                           │
│                  ▼                                                           │
│  ┌───────────────────────────────────────┐                                  │
│  │ Step 4: EXECUTE                       │                                  │
│  │ HTTP → Python /agent/execute          │                                  │
│  │ Fills form, clicks submit             │                                  │
│  └───────────────┬───────────────────────┘                                  │
│                  │                                                           │
│                  ▼                                                           │
│  ┌───────────────────────────────────────┐                                  │
│  │ Step 5: LOG RESULT                    │                                  │
│  │ Google Sheets → Update row status     │                                  │
│  │ (SUCCESS/ERROR + screenshot)          │                                  │
│  └───────────────────────────────────────┘                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Setup Instructions

1. **Import the Workflow**:
   ```
   n8n → Workflows → Import from File → internship_application.json
   ```

2. **Set Environment Variable**:
   - In n8n, go to **Settings → Environment Variables**
   - Add: `PYTHON_API_URL` = `http://your-server:8000`

3. **Configure Credentials**:
   - Google Sheets OAuth2 (for logging)
   - Google Gemini API (for AI brain)

4. **Link Sub-Workflow**:
   - Get the workflow ID of `Identity Fetcher`
   - Update "Step 2: Fetch Identity" node with the ID

5. **Configure Google Sheet**:
   - Create "Applications" sheet with columns:
   
   | row_id | url | status | applied_at | result_message | screenshot_url | actions_executed |
   |--------|-----|--------|------------|----------------|----------------|------------------|

#### Trigger Options

**Option A: Webhook**
```bash
curl -X POST http://your-n8n:5678/webhook/apply \
  -H "Content-Type: application/json" \
  -d '{"url": "https://company.com/apply", "row_id": 1}'
```

**Option B: Google Sheets**
- Enable the "Google Sheets Trigger" node
- Disable the "Webhook Trigger" node
- Add new rows to your Applications sheet

---

### 2. Identity Fetcher (`identity_fetcher.json`)

A **sub-workflow** that acts as a single source of truth for user profile data.

**Purpose**: Fetches and transforms user profile data from Google Sheets into a clean JSON object.

#### How It Works

```
Execute Workflow Trigger → Google Sheets (Read) → Code (Transform) → Output
```

#### Google Sheet Format ("User Profile" sheet)

| field_name | field_value |
|------------|-------------|
| full_name | John Doe |
| email | john@example.com |
| phone | +1 555-123-4567 |
| linkedin_url | https://linkedin.com/in/johndoe |
| github_url | https://github.com/johndoe |
| location | San Francisco, CA |

#### Output Format

```json
{
  "success": true,
  "profile": {
    "full_name": "John Doe",
    "email": "john@example.com",
    "linkedin_url": "https://linkedin.com/in/johndoe"
  }
}
```

#### Setup

1. Import `identity_fetcher.json` into n8n
2. Configure Google Sheets credentials
3. Select your spreadsheet and "User Profile" sheet

---

## Environment Variables (n8n)

| Variable | Description | Example |
|----------|-------------|---------|
| `PYTHON_API_URL` | URL of the Python FastAPI server | `http://localhost:8000` |

## Quick Start

1. Deploy Python API server on OCI VM
2. Import both workflows into n8n
3. Configure credentials and environment variables
4. Create Google Sheets with required structure
5. Trigger via webhook or add rows to Applications sheet

## Adding New Workflows

1. Create workflow in n8n UI
2. Export: **Workflows → Download**
3. Save to this directory
4. Document in this README

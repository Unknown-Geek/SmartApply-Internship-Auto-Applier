# n8n Workflows

This directory contains n8n workflow JSON files for SmartApply automation.

## Workflows

### Identity Fetcher (`identity_fetcher.json`)

A **sub-workflow** that acts as a single source of truth for user profile data.

**Purpose**: Fetch user identity from Google Sheets and return clean JSON.

**How it works**:
1. **Execute Workflow Trigger** - Makes this callable by other workflows
2. **Google Sheets Node** - Pulls all rows from "User Profile" sheet
3. **Code Node** - Transforms rows to clean JSON object

## Setup Instructions

### 1. Import the Workflow

1. Open n8n dashboard
2. Go to **Workflows** → **Import from File**
3. Select `identity_fetcher.json`

### 2. Configure Google Sheets

1. Click the "Get User Profile Data" node
2. Connect your Google Sheets OAuth2 credentials
3. Select your spreadsheet containing the "User Profile" sheet

### 3. Sheet Format

Your Google Sheet should have 2 columns:

| field_name     | field_value                    |
|----------------|--------------------------------|
| full_name      | John Doe                       |
| email          | john@example.com               |
| phone          | +1 555-123-4567                |
| linkedin_url   | https://linkedin.com/in/johnd  |
| github_url     | https://github.com/johndoe     |
| university     | MIT                            |
| degree         | BS Computer Science            |
| graduation     | May 2024                       |
| skills         | Python, JavaScript, React      |

### 4. Call from Other Workflows

In any other n8n workflow, use the **Execute Workflow** node:

```
Node: Execute Workflow
Workflow: Identity Fetcher
```

The output will be:
```json
{
  "success": true,
  "profile": {
    "full_name": "John Doe",
    "email": "john@example.com",
    "linkedin_url": "https://linkedin.com/in/johnd",
    ...
  },
  "fetched_at": "2024-01-27T16:00:00.000Z",
  "field_count": 9
}
```

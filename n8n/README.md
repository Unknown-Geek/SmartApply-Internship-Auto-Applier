# n8n Workflows

This directory contains n8n workflow definitions for the SmartApply automation system.

## Workflows

### Identity Fetcher (`identity_fetcher.json`)

A **sub-workflow** that acts as a single source of truth for user profile data.

**Purpose**: Fetches and transforms user profile data from Google Sheets into a clean JSON object that can be used by other workflows.

#### How It Works

```
┌─────────────────────────────┐
│ When Called by Another      │
│ Workflow (Trigger)          │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Google Sheets Node          │
│ - Reads "User Profile" sheet│
│ - Returns all rows          │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Code Node (Transform)       │
│ - Converts rows to JSON     │
│ - Keys → snake_case         │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Set Output                  │
│ - Returns profile to caller │
└─────────────────────────────┘
```

#### Google Sheet Format

Your "User Profile" sheet should have this structure:

| field_name | field_value |
|------------|-------------|
| full_name | John Doe |
| email | john@example.com |
| phone | +1 555-123-4567 |
| linkedin_url | https://linkedin.com/in/johndoe |
| github_url | https://github.com/johndoe |
| location | San Francisco, CA |
| ... | ... |

#### Output Format

```json
{
  "success": true,
  "fetched_at": "2024-01-27T10:30:00.000Z",
  "profile": {
    "full_name": "John Doe",
    "email": "john@example.com",
    "phone": "+1 555-123-4567",
    "linkedin_url": "https://linkedin.com/in/johndoe",
    "github_url": "https://github.com/johndoe",
    "location": "San Francisco, CA"
  },
  "field_count": 6
}
```

#### Setup Instructions

1. **Import the Workflow**:
   - In n8n, go to **Workflows → Import from File**
   - Select `identity_fetcher.json`

2. **Configure Google Sheets Credentials**:
   - Click on the "Read User Profile Sheet" node
   - Add your Google Sheets OAuth2 credentials
   - Select your spreadsheet document
   - Ensure sheet name is "User Profile"

3. **Test the Workflow**:
   - Click "Execute Workflow" to test
   - Verify the output JSON is correct

#### Calling from Other Workflows

Use the **Execute Workflow** node in your main workflow:

```
┌─────────────────────────────┐
│ Your Main Workflow          │
│                             │
│  ┌───────────────────────┐  │
│  │ Execute Workflow      │  │
│  │ → Identity Fetcher    │  │
│  └───────────┬───────────┘  │
│              │              │
│              ▼              │
│  ┌───────────────────────┐  │
│  │ Use $json.profile.*   │  │
│  │ in subsequent nodes   │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
```

Access fields like:
- `{{ $json.profile.full_name }}`
- `{{ $json.profile.email }}`
- `{{ $json.profile.linkedin_url }}`

## Adding New Workflows

1. Create your workflow in n8n
2. Export as JSON: **Workflows → Download**
3. Save to this directory with a descriptive name
4. Document in this README

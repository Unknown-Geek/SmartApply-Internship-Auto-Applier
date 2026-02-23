# SmartApply — Autonomous Internship Auto-Applier

An autonomous internship application agent powered by **Cerebras API** (`gpt-oss-120b` function-calling) + **Playwright** (headless browser), with **FastAPI**, **SQLite** memory, and fully autonomous browser automation. Designed for unattended operation — no Chrome extension required.

## Architecture

```
User ──► FastAPI REST API ──► SmartApply Orchestrator
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              Cerebras API    SQLite DB    Agent Memory
            (function-calling) (jobs, apps) (facts, profile)
                    │
            ┌───────┼───────┐
            ▼       ▼       ▼
        Playwright  Form    Page
        Browser    Filler  Analyzer
```

## Features

- **Cerebras Function-Calling Agent** — autonomous reasoning with tool use (browse, fill forms, click, screenshot)
- **Playwright Browser Automation** — fully headless Chromium, no extension needed
- **Full Application Pipeline** — search → analyze → fill → submit
- **SQLite Memory** — persistent job tracking, profile storage, agent memory
- **REST API** — complete FastAPI interface with Swagger docs

## Project Structure

```
SmartApply-Internship-Auto-Applier/
├── app/
│   ├── __init__.py              # Package init
│   ├── main.py                  # FastAPI app with all endpoints
│   ├── config.py                # Settings (pydantic-settings)
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── cerebras_agent.py   # Cerebras function-calling agent
│   │   ├── browser_manager.py  # Playwright browser manager
│   │   └── orchestrator.py     # Autonomous pipeline orchestrator
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py          # SQLite schema + CRUD operations
│   │   └── smartapply.db        # SQLite database (created at runtime)
│   └── services/
│       └── __init__.py
├── start.sh                     # Start script
├── requirements.txt             # Python dependencies
├── setup.sh                     # OCI VM setup script
├── .env.template                # Environment variables template
└── README.md
```

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-username/SmartApply-Internship-Auto-Applier.git
cd SmartApply-Internship-Auto-Applier

# 2. Set your Cerebras API key
cp .env.template .env
# Edit .env and set CEREBRAS_API_KEY=your-key-here

# 3. Install Python deps
pip install -r requirements.txt

# 4. Install Playwright browsers
playwright install chromium --with-deps

# 5. Start the server
chmod +x start.sh
./start.sh
```

The API will be available at `http://0.0.0.0:8000/docs`.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/`              | API info |
| GET    | `/health`        | Health check |
| POST   | `/agent/run`     | **Run a free-form agent task** (Cerebras + Playwright) |
| POST   | `/profile/ingest`| Parse resume text and store profile |
| GET    | `/profile`       | View stored profile |
| POST   | `/profile/set`   | Manually set a profile field |
| POST   | `/jobs/search`   | Search for internship listings |
| GET    | `/jobs`          | List discovered jobs |
| POST   | `/jobs/{id}/analyze` | Analyze a job's application page |
| POST   | `/jobs/{id}/apply`   | Apply to a specific job |
| POST   | `/pipeline/run`  | **Full automated pipeline** (search → analyze → apply) |
| GET    | `/stats`         | Dashboard statistics |
| POST   | `/memory`        | Store a fact in agent memory |
| GET    | `/memory`        | Recall facts |
| GET    | `/sessions`      | Agent session history |
| GET    | `/applications`  | Application attempts |

## Usage Examples

### Run a free-form agent task
```bash
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Go to https://example.com and tell me the page title"}'
```

### Ingest a resume
```bash
curl -X POST http://localhost:8000/profile/ingest \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "John Doe, john@example.com, B.Tech CS from IIT..."}'
```

### Run the full pipeline
```bash
curl -X POST http://localhost:8000/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "criteria": "Software Engineering Intern, Remote, Python",
    "max_applications": 3,
    "auto_apply": false
  }'
```

### Check stats
```bash
curl http://localhost:8000/stats
```

## Configuration

| Variable | Description | Required |
|----------|-------------|----------|
| `CEREBRAS_API_KEY` | Cerebras API key | Yes |
| `CEREBRAS_MODEL` | Model name (default: `gpt-oss-120b`) | No |
| `APP_ENV` | Environment (default: development) | No |
| `PORT` | Server port (default: 8000) | No |
| `HEADLESS` | Run browser headless (default: true) | No |
| `MAX_AGENT_STEPS` | Max agent reasoning steps (default: 25) | No |
| `AGENT_TIMEOUT_SECONDS` | Agent timeout (default: 600) | No |

## How It Works

1. **Profile Ingestion** — parse your resume via Cerebras LLM, store structured data in SQLite
2. **Job Search** — agent browses job boards using Playwright, extracts listings
3. **Job Analysis** — agent visits each application page, maps form fields using `extract_page_data`
4. **Application** — agent fills forms using `fill_form`, uploads resume, clicks submit
5. **Memory** — facts learned across sessions persist in SQLite for context

The agent uses Cerebras's **function-calling** capability (OpenAI-compatible) to autonomously decide when to browse, fill forms, click buttons, and take screenshots. All browser automation is handled by Playwright (headless Chromium) — no browser extension or manual setup required.

## License

MIT

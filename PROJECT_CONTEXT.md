# Smart Apply — Project Context

> Quick-reference for anyone (human or AI) jumping into this codebase.
> Last updated: 2026-04-12

---

## What It Does

Smart Apply is an autonomous job-application agent. You paste a job URL, and a headless browser agent (powered by a local LLM via Ollama) navigates the application form, fills it with your identity data, and submits it — while you watch every step in real time through a web dashboard.

---

## Architecture Overview

```
┌─────────────┐    WS + REST    ┌──────────────┐    HTTP     ┌──────────┐
│   Frontend   │◄──────────────►│    Backend    │◄───────────►│  Ollama  │
│  React/Vite  │  :3005→:80     │  FastAPI      │  :11434    │ qwen2.5  │
│  nginx proxy │                │  + browser-use│            │  coder:7b│
└─────────────┘                 │  + PinchTab   │            └──────────┘
                                │  + Scrapling   │
                                └──────┬────────┘
                                       │ HTTP
                                ┌──────▼────────┐
                                │  context-mode  │
                                │  Node.js FTS5  │
                                │  :3100         │
                                └───────────────┘
```

All services run in Docker on an ARM64 (Oracle Ampere) VM. The LLM runs 100% locally — no cloud API keys needed.

---

## Services (docker-compose.yml)

| Service | Image/Build | Port | Purpose |
|---------|-------------|------|---------|
| **ollama** | `ollama/ollama:latest` | 11434 | Local LLM inference. Auto-pulls `qwen2.5-coder:7b` (~4.1 GB) on first boot |
| **context-mode** | `./context-mode` | 3100 | SQLite FTS5 index for DOM/JD text. Node.js + `better-sqlite3` |
| **backend** | `./backend` | 8000 | FastAPI app. Runs the browser-use agent in a thread pool |
| **frontend** | `./frontend` | 3005→80 | React SPA served by nginx. Proxies `/api/` and `/ws/` to backend |

---

## Backend Structure (`backend/app/`)

```
app/
├── main.py              # FastAPI entrypoint, lifespan, CORS, router registration
├── core/
│   └── config.py        # Pydantic Settings (reads .env)
├── agent/
│   ├── agent.py         # browser-use Agent orchestration, retries, event loop fix
│   ├── human_input.py   # Thread-safe pause/resume for mid-run human Q&A
│   ├── tools.py         # smolagents @tool wrappers (Scrapling, PinchTab, ctx_search) — LEGACY, not used by browser-use
│   └── prompt.py        # System prompt template for CodeAgent — LEGACY, not used by browser-use
├── api/
│   ├── health.py        # GET /api/health — deep check (Ollama, context-mode, PinchTab)
│   ├── jobs.py          # POST /api/jobs/apply, GET /{id}, POST /{id}/answer, GET /waiting
│   ├── identity.py      # GET/POST /api/identity — CSV upload, profile ingest from n8n
│   └── ws.py            # WS /ws/agent/{task_id} — live log streaming + status heartbeats
├── data/
│   └── identity.py      # Load CSV → dict, compact core-field filter, JSON profile ingest
└── models/
    └── schemas.py       # Pydantic models: TaskStatus, TaskResponse, HealthResponse, etc.
```

### Key Backend Details

- **Agent runtime** (`agent.py`): Uses `browser-use` library's `Agent` class with `ChatOllama` (langchain-ollama). Runs in `ThreadPoolExecutor` with its own `asyncio.new_event_loop()` (not `asyncio.run()` — that crashes in threads). 2 retries with backoff on transient errors.
- **Human-in-the-loop** (`human_input.py`): `request_input()` blocks the agent thread with a `threading.Event`. `provide_answer()` unblocks it from the REST API. 5-min default timeout.
- **Identity** (`identity.py`): Two modes — CSV upload (`load_identity`) or JSON profile from n8n (`ingest_profile_json`). `get_identity_text(compact=True)` filters to ~35 core fields to avoid overflowing the 8K context window.
- **WebSocket** (`ws.py`): Polls `_tasks` dict every 1s, sends new logs + status heartbeat. When status is `waiting`, includes the `question` field.
- **Supervisord** (`supervisord.conf`): Manages Xvfb (display :99), PinchTab daemon, and uvicorn inside the backend container.
- **Config** (`config.py`): Pydantic Settings class, but most modules read env vars directly via `os.getenv()`. Both patterns coexist.

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Deep health check (Ollama, context-mode, PinchTab status) |
| POST | `/api/jobs/apply` | Submit job URL → returns task_id |
| GET | `/api/jobs/{id}` | Get task status + logs |
| POST | `/api/jobs/{id}/answer` | Provide human answer when agent is waiting |
| GET | `/api/jobs/waiting` | List tasks waiting for human input |
| GET | `/api/jobs/` | List all tasks |
| WS | `/ws/agent/{id}` | Live log stream |
| GET | `/api/identity` | View loaded identity |
| POST | `/api/identity/csv` | Upload CSV |
| POST | `/api/identity/resume` | Upload resume PDF |
| POST | `/api/profile/ingest/direct` | Ingest JSON profile from n8n |

---

## Frontend Structure (`frontend/src/`)

```
src/
├── App.tsx               # Main app: health check, job submit, terminal, human-input panel
├── App.css               # Layout + animated background + human-input panel styles
├── index.css             # CSS variables, global styles
├── components/
│   ├── AgentTerminal.tsx  # Log viewer with color-coded levels
│   ├── HealthBar.tsx      # Service status dots (Ollama, context-mode, PinchTab)
│   ├── IdentityPanel.tsx  # Upload CSV/resume, show loaded fields
│   ├── JobInput.tsx       # URL input + submit button
│   ├── StatusBadge.tsx    # Colored badge: pending/running/waiting/completed/failed
│   └── TaskHistory.tsx    # Sidebar list of past tasks
└── hooks/
    └── useAgentSocket.ts  # WebSocket hook: logs, status, result, error, question
```

### Key Frontend Details

- Built with Vite + React + TypeScript. Served by nginx in Docker.
- nginx proxies `/api/` and `/ws/` to the backend container.
- `useAgentSocket` hook returns `question` when agent is in `waiting` state, enabling the human-input panel.
- Env vars: `VITE_API_URL`, `VITE_WS_URL` (set at build time).

---

## Context-Mode (`context-mode/`)

Lightweight Node.js server (no framework — raw `http` module) providing SQLite FTS5 full-text search. Used by the agent to avoid flooding the LLM context with raw DOM text. Endpoints: `/index`, `/search`, `/clear`, `/health`. Splits content into 2000-char chunks for better recall.

---

## n8n Workflows (`n8n/`)

Six n8n workflow JSONs for external automation:

| Workflow | Purpose |
|----------|---------|
| Profile Sync (Trigger) | Webhook that receives applicant data and POSTs to `/profile/ingest/direct` |
| Identity Fetcher | Scrapes/fetches applicant profile data |
| Application Logger | Receives POST from backend after each agent run → logs to Google Sheets |
| Telegram QA | Receives questions from agent mid-run → sends to Telegram |
| Telegram Reply Listener | Receives Telegram replies → POSTs answer to `/api/jobs/{id}/answer` |
| Queue Application | Job queue management |

**Important**: These contain real webhook URLs. They are gitignored but some were previously tracked. The `.env.example` has the n8n webhook URL structure.

---

## Data Directory (`data/`)

```
data/
├── identity/
│   ├── identity.csv          # Applicant identity (field,value columns) — GITIGNORED
│   ├── identity.example.csv  # Example template
│   └── resume.pdf            # Applicant resume — GITIGNORED
└── sessions/
    └── *.json                 # Agent session logs — persisted per task
```

The `data/` directory is bind-mounted into the backend container (`./data:/app/data`).

---

## Key Design Decisions & Gotchas

1. **browser-use, not smolagents**: The project originally used `smolagents` CodeAgent with custom tools (`tools.py`, `prompt.py`). It now uses `browser-use`'s `Agent` which has its own browser automation. The old smolagents tools are still in the codebase but unused.
2. **ARM64 inference is slow**: `timeout=180` on ChatOllama (default 75s is too short). Compact identity text to fit 8K context.
3. **Event loop in threads**: `asyncio.run()` crashes inside `ThreadPoolExecutor`. Must use `asyncio.new_event_loop()` + `loop.run_until_complete()`.
4. **Thread-local for user_input_fn**: The `ask_user()` controller action uses `threading.local()` to access the per-task callback without a global.
5. **PinchTab is optional**: The supervisord config allows PinchTab to fail (exitcodes 0,1,2). If PinchTab is down, the agent still works via browser-use's native Playwright.
6. **No Skyvern**: Previously had a Skyvern fallback engine — removed. The docker-compose still had the service definition until the latest commit.
7. **Frontend port**: Changed from 3000 to 3005 to avoid conflicts with common dev servers.

---

## Environment Variables

See `.env.example` for the full list. Key ones:

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama API URL |
| `LLM_MODEL` | `qwen2.5-coder:7b` | Model name |
| `LLM_CONTEXT_SIZE` | `8192` | Context window |
| `AGENT_MAX_STEPS` | `20` | Max browser-use steps |
| `N8N_LOG_WEBHOOK_URL` | (empty) | Webhook for application logging |
| `N8N_QUESTION_WEBHOOK_URL` | (empty) | Webhook for Telegram Q&A |
| `VITE_API_URL` | `http://localhost:8000` | Frontend → Backend URL |
| `VITE_WS_URL` | `ws://localhost:8000` | Frontend → WebSocket URL |

---

## Makefile Targets

`up`, `down`, `dev`, `logs`, `logs-backend`, `pull-model`, `build`, `health`, `setup-data`, `clean`, `clean-sessions`, `push`

---

## CI (`.github/workflows/ci.yml`)

Four parallel jobs on push/PR to main:
1. **Validate Docker Compose** — `docker compose config --quiet`
2. **Backend Lint** — `ruff check backend/app/ --ignore E501`
3. **Frontend Type Check** — `tsc --noEmit` + `vite build`
4. **context-mode Syntax** — `node --check server.js`

---

## Recent Fixes (as of 2026-04-12)

- Fixed `ChatOllama` constructor (`base_url` instead of `host`, `timeout=180`)
- Fixed `asyncio.run()` crash in ThreadPoolExecutor
- Added compact identity text (core fields filter) for 8K context
- Fixed `HealthResponse` schema (nested `ServiceStatus` instead of `ollama: bool`)
- Added human-input UI panel in frontend (question display + answer input)
- Surfaced `question` from WS heartbeat in `useAgentSocket` hook
- Removed Skyvern service from docker-compose
- Removed orphaned `app_data` volume, switched to `./data` bind mount
- Added `waiting` status to `StatusBadge`
- Deleted stale failed session JSONs

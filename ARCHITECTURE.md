# 🤖 Smart Apply — Architecture & Implementation Guide

> **Auto Job Application Agent** — Fills and submits job applications autonomously using a local LLM, agentic browser control, and context-aware DOM parsing.

---

## 🔬 Model Selection

Hardware profile of the target VM (Oracle Cloud / ARM Neoverse-N1):

| Property        | Value                        |
|-----------------|------------------------------|
| CPU             | ARM Neoverse-N1 (4 cores)   |
| Total RAM       | 23.4 GB                      |
| Available RAM   | ~13.6 GB                     |
| GPU             | None                         |
| Backend         | CPU (ARM)                    |
| OS              | Ubuntu 22.04 (aarch64)       |

**Chosen: `qwen3:8b` (via Ollama)**

Why qwen3:8b over the previous qwen2.5-coder:7b:

| Aspect | qwen2.5-coder:7b | qwen3:8b |
|--------|-------------------|----------|
| Context window | 8K | 32K |
| Specialization | Code generation | Instruction following + tool calling |
| Size (Q4) | ~4.1 GB | ~4.9 GB |
| Agentic capability | Moderate | Strong (built-in thinking mode) |
| Identity prompt | Must compact to core fields | Full profile fits easily |

- 32K context eliminates the need for compact identity text and avoids context overflow
- Built-in thinking mode (`/think`) improves form-filling accuracy on complex multi-step applications
- Slightly larger footprint (~4.9 GB vs ~4.1 GB) but still within the RAM envelope

> **llmfit** can be re-run anytime: `docker run ghcr.io/alexsjones/llmfit recommend --use-case coding --json`

---

## 🏛️ 1. High-Level Architecture (Agentic Browser Automation)

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose Stack                     │
│                                                             │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  Ollama  │◄───│   Backend    │    │    Frontend      │  │
│  │  :11434  │    │  (FastAPI)   │    │  (React/Vite)    │  │
│  │          │    │   :8000      │    │    :3005         │  │
│  └──────────┘    └──────┬───────┘    └──────────────────┘  │
│        │                │                      │            │
│   qwen3:8b     ┌────────▼──────┐     WebSocket logs        │
│  (auto-pulled  │ browser-use   │                           │
│   on first     │ Agent+Browser │                           │
│   boot)        └────┬──────────┘                           │
│                ┌────────┴─────────┐                        │
│                │                  │                        │
│         ┌──────▼───┐    ┌─────────▼────┐                  │
│         │ PinchTab │    │ context-mode  │                  │
│         │ (Chrome) │    │ (SQLite FTS5) │                  │
│         └──────────┘    └──────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

**Component Roles:**

| Component | Role | Tech |
|-----------|------|------|
| **Orchestrator** | Manages See-Think-Act loop | browser-use Agent |
| **Brain** | Reads pages, decides actions, fills forms | qwen3:8b via Ollama |
| **Context Engine** | Indexes DOM, answers semantic queries | context-mode (SQLite FTS5) |
| **Recon (Eyes)** | Scrapes job descriptions, bypasses anti-bot | Scrapling |
| **Hands** | Headless Chrome, token-efficient refs | PinchTab / Playwright |
| **Bridge** | Session management, WebSocket streaming | FastAPI + Uvicorn |
| **Interface** | React dashboard with live agent view | React + Vite |

---

## 💻 2. Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, Uvicorn, browser-use |
| Local AI | Ollama, qwen3:8b (32K context) |
| Browser/Scraping | browser-use (Playwright), PinchTab, Scrapling |
| Optimization | context-mode (Node.js, SQLite FTS5) |
| Frontend | React 18, Vite, TypeScript |
| Containerization | Docker Compose v2 |
| Process Manager | Supervisor (inside backend container) |

---

## 📦 3. Containerization (Single-Command Install)

Everything runs via Docker Compose. Users install with **one command**:

```bash
git clone https://github.com/youruser/smart-apply.git && cd smart-apply && docker compose up -d
```

### Container Layout

```yaml
# docker-compose.yml overview
services:
  ollama:          # Pulls qwen3:8b on first boot
  backend:         # FastAPI + browser-use + PinchTab + Scrapling
  context-mode:    # Context indexing server (Node.js)
  frontend:        # React/Vite dashboard
```

### Model Auto-Pull on Start
The Ollama container uses an entrypoint script that auto-pulls the model:
```bash
ollama pull qwen3:8b  # ~4.9 GB download on first run
```

### Volume Persistence
```
ollama_data    → /root/.ollama      (model weights, ~4.9 GB)
./data         → /app/data          (identity CSV, session logs)
chrome_data    → /app/.chrome_data  (browser profile)
```

---

## 🗺️ 4. Detailed Implementation

### Phase 1: Infrastructure & MCP Layer Setup

**Ollama Setup (containerized):**
- ARM-compatible Ollama image (`ollama/ollama:latest` supports `linux/arm64`)
- Entrypoint waits for API readiness then triggers model pull
- Binds to `ollama:11434` on Docker internal network
- Backend container uses `OLLAMA_HOST=http://ollama:11434`

**PinchTab Setup:**
- Installed inside backend container via `curl -fsSL https://pinchtab.com/install.sh | bash`
- Chromium/Chromium-driver installed for ARM64 (`chromium-browser`)
- PinchTab daemon runs under Supervisor inside the container

**context-mode Setup:**
- Runs as a dedicated lightweight Node.js container
- Exposes HTTP API for indexing and searching
- SQLite FTS5 database persisted in a volume

**Scrapling Setup:**
- Installed in backend Python environment: `pip install "scrapling[all]"`
- `scrapling install` run at container build time (fetches browser fingerprints)

### Phase 2: FastAPI Backend

```
backend/
├── app/
│   ├── main.py           # FastAPI entrypoint, lifespan, CORS
│   ├── api/
│   │   ├── jobs.py       # POST /api/jobs/apply, GET /api/jobs/{id}, POST /{id}/answer
│   │   ├── health.py     # GET /api/health — deep service check
│   │   ├── identity.py   # Identity CSV upload, profile ingest from n8n
│   │   └── ws.py         # WS /ws/agent/{task_id}
│   ├── agent/
│   │   ├── agent.py      # browser-use Agent orchestration
│   │   ├── human_input.py # Thread-safe pause/resume for human Q&A
│   │   ├── tools.py      # Legacy smolagents tools (unused by browser-use)
│   │   └── prompt.py     # Legacy system prompt (unused by browser-use)
│   ├── core/
│   │   ├── config.py     # Pydantic Settings (env vars)
│   │   └── auth.py       # API key authentication middleware
│   ├── models/
│   │   └── schemas.py    # Pydantic schemas
│   └── data/
│       └── identity.py   # CSV loader, JSON profile ingest, compact text
├── requirements.txt
└── Dockerfile
```

**Key Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/jobs/apply` | Submit job URL, spawn background agent task |
| `GET` | `/api/jobs/{task_id}` | Get task status + partial logs |
| `POST` | `/api/jobs/{task_id}/answer` | Provide human answer when agent is waiting |
| `GET` | `/api/jobs/waiting` | List tasks waiting for human input |
| `GET` | `/api/jobs/queue/status` | Queue position, active count, max concurrency |
| `WS` | `/ws/agent/{task_id}` | Live stream of agent thoughts & actions |
| `GET` | `/api/health` | Deep health check (Ollama, context-mode, PinchTab, model info) |
| `GET` | `/api/ollama/stats` | Live Ollama stats — VRAM, running models, model details |

### Phase 3: browser-use Agent

```python
from browser_use import Agent, Browser, ChatOllama, Controller

model = ChatOllama(
    model="qwen3:8b",
    base_url="http://ollama:11434",
    temperature=0.1,
    num_ctx=32768,           # Full 32K context — fits identity + DOM
    timeout=180,             # 3 min — ARM inference is slow
)

browser = Browser(headless=True)
agent = Agent(
    task=task,
    llm=model,
    browser=browser,
    controller=controller,   # Registers ask_user(), download_file_from_drive()
    max_actions_per_step=3,
)
result = loop.run_until_complete(agent.run(max_steps=20))
```

**Task Prompt:**
> "Apply for the job at: {url}. Here is the applicant's identity data. Use it to fill form fields. Instructions: 1. Go to the job application URL. 2. Read the page, find form fields, and fill them using the identity data. 3. For fields not in the identity data, use ask_user() to ask the human. 4. Click Next/Continue to advance through multi-step forms. 5. Stop when you see a submission confirmation message."

### Phase 4: Frontend

```
frontend/
├── src/
│   ├── App.tsx               # Main app + human-input panel
│   ├── components/
│   │   ├── JobInput.tsx       # URL input + submit button
│   │   ├── AgentTerminal.tsx  # Live WebSocket log viewer
│   │   ├── StatusBadge.tsx    # Pending/Running/Waiting/Completed/Failed
│   │   ├── HealthBar.tsx      # Service status dots
│   │   ├── IdentityPanel.tsx  # Upload CSV/resume, show loaded fields
│   │   └── TaskHistory.tsx    # Past task list
│   ├── hooks/
│   │   └── useAgentSocket.ts  # WebSocket hook (logs, status, question)
│   └── App.css                # Layout + animations
├── package.json
├── nginx.conf                 # Proxies /api/ and /ws/ to backend
└── Dockerfile
```

---

## ⚠️ 5. Key Considerations & Optimization

### Context Management
- qwen3:8b supports 32K context — full identity profile + page DOM fits without truncation
- Legacy compact mode still available via `get_identity_text(compact=True)` for smaller models
- `get_ui_elements()` can return 50 KB+ for complex Workday forms — pipe through context-mode

### Human-in-the-Loop
- Agent calls `ask_user(question)` when it encounters fields not in identity data
- Blocks agent thread via `threading.Event` until operator answers
- Frontend shows question + answer input when status is `waiting`
- Optional n8n → Telegram relay for mobile notifications

### File Upload Handling
- `<input type="file">` bypasses OS picker via PinchTab's file attachment API
- Resume PDF path injected via `RESUME_PDF_PATH` env var
- Google Drive URLs auto-downloaded via `gdown` CLI

### Token & Step Limits
- `max_steps=20` hard cap in browser-use Agent
- `num_ctx=32768` in Ollama (full qwen3 context window)
- `timeout=180` on ChatOllama (3 min — ARM inference is slow)
- If model is slow, drop to `qwen3:4b` (faster, 32K context, less capable)

### Job Queue & Concurrency
- Semaphore-based queue limits concurrent agent runs (`MAX_CONCURRENT_AGENTS=1` by default)
- ARM64 VM with 4.9 GB model can only handle 1 LLM session at a time
- Jobs exceeding the limit are queued and start when a slot opens
- Queue status visible via `GET /api/jobs/queue/status`
- Frontend shows `~N steps/min` during active agent runs

### API Key Authentication
- `API_KEYS` env var (comma-separated) — leave empty to disable auth
- Supports query param (`?api_key=KEY`), `X-API-Key` header, or `Authorization: Bearer KEY`
- Health endpoint (`/api/health`) is always public
- WebSocket connections bypass the middleware

### ARM-Specific Optimizations
- Ollama `OLLAMA_NUM_PARALLEL=1` (avoid OOM with 4 cores)
- `OLLAMA_NUM_THREAD=4` (use all ARM cores)
- PinchTab runs headless Chromium in `--no-sandbox` (container-safe)
- Q4 quantization (best quality/speed on ARM without GPU)
- `asyncio.new_event_loop()` in ThreadPoolExecutor (not `asyncio.run()` — crashes in threads)

### Anti-Bot Bypass
- Scrapling handles Cloudflare-protected job boards (LinkedIn etc.)
- PinchTab uses real Chromium user-agent, not puppeteer fingerprint

---

## 🐳 6. Docker Compose Single-Command Deploy

```bash
# Clone & launch everything
git clone https://github.com/youruser/smart-apply.git
cd smart-apply
docker compose up -d

# First run: model pull takes ~5-10 min depending on connection
# Follow pull progress:
docker logs -f smart-apply-ollama-1

# Open dashboard
open http://localhost:3005
```

**Services after `docker compose up -d`:**

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3005 | React dashboard |
| Backend API | http://localhost:8000 | FastAPI + Swagger docs |
| Ollama | http://localhost:11434 | LLM inference API |
| context-mode | (internal) | Context indexing server |

---

## 📁 7. Project Structure

```
smart-apply/
├── docker-compose.yml          ← Single-command launch
├── .env.example               ← Config template
├── ARCHITECTURE.md            ← This file
├── PROJECT_CONTEXT.md          ← Quick-reference context doc
├── PROGRESS.md                ← Build progress log
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── supervisord.conf        ← Runs FastAPI + PinchTab daemon
│   └── app/
│       ├── main.py
│       ├── api/
│       ├── agent/
│       ├── models/
│       └── data/
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── nginx.conf
│   └── src/
│
├── context-mode/
│   └── Dockerfile              ← Node.js context indexing server
│
├── ollama/
│   └── entrypoint.sh          ← Auto-pulls qwen3:8b
│
├── n8n/                        ← n8n workflow JSONs
│
└── data/
    └── identity/              ← Mounted volume for user CSV/resume
```

---

## 🔄 8. Development vs Production

| Mode | Command | Notes |
|------|---------|-------|
| Dev | `docker compose -f docker-compose.dev.yml up` | Hot-reload backend/frontend |
| Prod | `docker compose up -d` | Optimized, no source mounts |

---

*Last updated: 2026-04-12 | Model: qwen3:8b (32K context) on Oracle Cloud ARM VM*

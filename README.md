# ⚡ Smart Apply

> **Autonomous AI job application agent** — Paste a URL, watch it apply.

Powered by `qwen3:8b` running locally via Ollama. No cloud API keys required. 100% private.

---

## 🚀 Quick Start (Single Command)

```bash
git clone https://github.com/Unknown-Geek/smart-apply.git
cd smart-apply

# 1. Copy and edit your identity
cp .env.example .env
# Edit data/identity/identity.csv with your details
# Copy your resume PDF to data/identity/resume.pdf

# 2. Launch everything
docker compose up -d

# First run: downloads qwen3:8b (~4.9 GB). Follow progress:
docker logs -f smart-apply-ollama

# 3. Open the dashboard
open http://localhost:3005
```

That's it. Everything — Ollama, the AI model, FastAPI backend, context indexer, and React dashboard — runs in containers.

---

## 🤖 How It Works

```
You paste a job URL
       ↓
Scrapling scrapes the job description (bypasses Cloudflare/LinkedIn)
       ↓
qwen3:8b reads the JD + your identity data (32K context window)
       ↓
browser-use opens headless Chrome → reads and fills form fields
       ↓
Agent fills each field → clicks Next → repeat until Submit
       ↓
You see every thought and action live in the dashboard
```

### Why these tools?

| Tool | Why |
|------|-----|
| `qwen3:8b` | Strong instruction following + 32K context — fits full identity + page DOM without truncation |
| Scrapling | Bypasses Cloudflare & LinkedIn anti-bot |
| browser-use | Native Playwright agent with LLM-driven form navigation |
| context-mode | SQLite FTS5 index for large DOM text — agent queries instead of reading walls of HTML |
| PinchTab | Token-efficient DOM refs (e5 not `<button class="...">`) |

---

## 📁 Your Identity Data

Edit `data/identity/identity.csv`:

```csv
field,value
first_name,Your First Name
last_name,Your Last Name
email,you@email.com
phone,+1-555-0000
...
```

Copy your resume: `cp /path/to/resume.pdf data/identity/resume.pdf`

---

## 🐳 Services

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | http://localhost:3005 | React UI |
| API | http://localhost:8000 | FastAPI + Swagger |
| Ollama | http://localhost:11434 | LLM inference |

---

## 🔧 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `qwen3:8b` | Ollama model to use |
| `LLM_CONTEXT_SIZE` | `32768` | Context window (qwen3 supports up to 32K) |
| `AGENT_MAX_STEPS` | `20` | Max agent steps before giving up |
| `N8N_LOG_WEBHOOK_URL` | *(empty)* | n8n webhook to log results (optional) |

See `.env.example` for all options.

---

## 🔗 n8n Automation (Optional)

Smart Apply ships with ready-to-import **n8n** workflow JSONs in the `n8n/` directory that wire it to Google Sheets and Telegram:

| Workflow | What it does |
|----------|-------------|
| **Identity Fetcher** | Sub-workflow: reads your profile Google Sheet → structured JSON |
| **Profile Sync (Trigger)** | Polls sheet daily → `POST /profile/ingest/direct` to hot-reload identity |
| **Queue Application** | Webhook: receive a job URL → append to queue sheet |
| **Application Logger** | Webhook: receive result → log to Sheets + Telegram notification |
| **Telegram Q&A** | Receives agent questions mid-run → sends to Telegram |
| **Telegram Reply Listener** | Receives Telegram replies → answers the agent |

### Setup steps
1. Import each JSON into your n8n instance (**Workflows → Import from file**)
2. Set your Google Sheets & Telegram credentials in n8n
3. Update the backend host IP in **Profile Sync** (`172.18.0.1` = Docker bridge default on Linux)
4. Set `N8N_LOG_WEBHOOK_URL` in your `.env` to enable result logging

```
GET  /profile/schema          ← shows expected profile JSON shape
POST /profile/ingest/direct   ← n8n pushes profile here (auto-reloads identity)
```

## 🖥️ Hardware Requirements

This setup was optimized for ARM64 inference:
- **Minimum**: 4 CPU cores, 16 GB RAM, no GPU required
- **Recommended**: 8+ CPU cores, 24 GB RAM
- **Tested on**: Oracle Cloud ARM (Neoverse-N1, 4 cores, 24 GB RAM)

Model can be swapped for faster/smaller options:
- `qwen3:4b` — faster, 32K context, less capable on complex forms
- `gemma3:4b` — fastest, 14K context, good for simple applications
- `qwen3:14b` — most capable, needs 16+ GB free RAM

---

## 📋 Tracking Progress

See [PROGRESS.md](./PROGRESS.md) for build log and session notes.
See [ARCHITECTURE.md](./ARCHITECTURE.md) for technical deep-dive.

---

*Built with qwen3 • browser-use • PinchTab • Scrapling • context-mode*

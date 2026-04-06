# 🤖 Smart Apply — Architecture & Implementation Guide

> **Auto Job Application Agent** — Fills and submits job applications autonomously using a local LLM, agentic browser control, and context-aware DOM parsing.

---

## 🔬 Model Selection (via llmfit)

Hardware profile of the target VM (Oracle Cloud / ARM Neoverse-N1):

| Property        | Value                        |
|-----------------|------------------------------|
| CPU             | ARM Neoverse-N1 (4 cores)   |
| Total RAM       | 23.4 GB                      |
| Available RAM   | ~13.6 GB                     |
| GPU             | None                         |
| Backend         | CPU (ARM)                    |
| OS              | Ubuntu 22.04 (aarch64)       |

**llmfit** was used to evaluate hundreds of models against this hardware profile. For a **coding + agentic** use case on CPU-only ARM:

| Rank | Model                         | Score | Est. TPS | RAM Req | Fit      | Quant  |
|------|-------------------------------|-------|----------|---------|----------|--------|
| 🥇 1 | **qwen2.5-coder:7b** (Q4_K_M) | 76.2  | ~9.5     | ~9.0 GB | Marginal | Q4_K_M |
| 2    | qwen2.5-coder:3b (Q4_K_M)    | 73.1  | ~23.3    | ~3.9 GB | Marginal | Q4_K_M |
| 3    | starcoder2-7b (Q4_K_M)       | 76.0  | ~10.0    | ~8.5 GB | Marginal | Q8_0   |

**Chosen: `qwen2.5-coder:7b` (Q4_K_M via Ollama)**
- Best quality/speed tradeoff for coding agents on CPU-only ARM
- 9.5 tok/s: acceptable for agentic loops (not interactive chat)
- 9 GB footprint leaves ~4.6 GB for the rest of the stack
- Confirmed via llmfit's multi-dimensional scoring (Quality=83, Fit=100, Context=100)

> **llmfit** can be re-run anytime: `docker run ghcr.io/alexsjones/llmfit recommend --use-case coding --json`

---

## 🏛️ 1. High-Level Architecture (Text-Driven Agentic DOM)

We bypass the slower Vision-Language Model (VLM) approach in favor of a lightning-fast, code-generating LLM pipeline.

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose Stack                     │
│                                                             │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  Ollama  │◄───│   Backend    │    │    Frontend      │  │
│  │  :11434  │    │  (FastAPI)   │    │  (React/Vite)    │  │
│  │          │    │   :8000      │    │    :3000         │  │
│  └──────────┘    └──────┬───────┘    └──────────────────┘  │
│        │                │                      │            │
│  qwen2.5-coder:7b  ┌────▼──────┐     WebSocket logs        │
│  (Q4_K_M, pulled   │ smolagents│                           │
│   on first boot)   │ CodeAgent │                           │
│                    └────┬──────┘                           │
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
| **Orchestrator** | Manages See-Think-Act loop | smolagents CodeAgent |
| **Brain** | Writes & runs Python to fill forms | qwen2.5-coder:7b via Ollama |
| **Context Engine** | Indexes DOM, answers semantic queries | context-mode (SQLite FTS5) |
| **Recon (Eyes)** | Scrapes job descriptions, bypasses anti-bot | Scrapling |
| **Hands** | Headless Chrome, token-efficient refs | PinchTab |
| **Bridge** | Session management, WebSocket streaming | FastAPI + Uvicorn |
| **Interface** | React dashboard + CLI via Ink | React, Ink |

---

## 💻 2. Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, Uvicorn, smolagents |
| Local AI | Ollama, qwen2.5-coder:7b (Q4_K_M) |
| Browser/Scraping | PinchTab (Golang binary), Scrapling |
| Optimization | context-mode (Node.js/TypeScript, SQLite FTS5) |
| Frontend | React 18, Vite, TailwindCSS, Ink (CLI) |
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
  ollama:          # Pulls qwen2.5-coder:7b on first boot
  backend:         # FastAPI + smolagents + PinchTab + Scrapling
  context-mode:    # MCP context indexing server (Node.js)
  frontend:        # React/Vite dashboard
```

### Model Auto-Pull on Start
The Ollama container uses an entrypoint script that auto-pulls the model:
```bash
ollama pull qwen2.5-coder:7b  # ~4.1 GB download on first run
```

### Volume Persistence
```
ollama_data    → /root/.ollama      (model weights, ~4.1 GB)
app_data       → /app/data          (identity CSV, session logs)
chrome_data    → /app/.chrome_data  (browser profile)
```

---

## 🗺️ 4. Detailed Implementation Plan

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
- Exposes MCP tools over stdio / local socket
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
│   │   ├── jobs.py       # POST /api/jobs/apply, GET /api/jobs/{id}
│   │   └── ws.py         # WS /ws/agent/{task_id}
│   ├── agent/
│   │   ├── tools.py      # scrape_jd, navigate, get_ui_elements, act_on_ui
│   │   ├── agent.py      # smolagents CodeAgent initialization
│   │   └── prompt.py     # System prompt / Prime Directive
│   ├── models/
│   │   └── schemas.py    # Pydantic schemas
│   └── data/
│       └── identity.py   # CSV loader (pandas)
├── requirements.txt
└── Dockerfile
```

**Key Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/jobs/apply` | Submit job URL, spawn background agent task |
| `GET` | `/api/jobs/{task_id}` | Get task status + partial logs |
| `WS` | `/ws/agent/{task_id}` | Live stream of agent thoughts & actions |
| `GET` | `/api/health` | Health check |

### Phase 3: smolagents Loop

```python
from smolagents import CodeAgent, LiteLLMModel

# Point to containerized Ollama
model = LiteLLMModel(
    model_id="ollama/qwen2.5-coder:7b",
    api_base="http://ollama:11434",
    num_ctx=8192,            # Balanced — llmfit recommends ≤8192 for this RAM
    temperature=0.1,         # Low temp for deterministic form-filling
)

agent = CodeAgent(
    tools=[scrape_jd, navigate, get_ui_elements, act_on_ui, ctx_search],
    model=model,
    max_steps=20,            # Hard cap — prevents infinite loops on broken forms
    additional_authorized_imports=["json", "re", "time"],
)
```

**System Prompt (Prime Directive):**
> "You are an autonomous job application agent. You have the applicant's Identity Data (name, email, phone, resume path, skills). Steps: (1) scrape_jd(url) to understand the role. (2) navigate(url) to open the application. (3) Loop: get_ui_elements() → match fields to Identity Data → act_on_ui() to fill/click. (4) If DOM output is large, use ctx_search(query) instead of reading raw. (5) Stop at Submit confirmation. Never loop more than 20 steps."

### Phase 4: Frontend

```
frontend/
├── src/
│   ├── App.tsx
│   ├── components/
│   │   ├── JobInput.tsx       # URL input + submit button
│   │   ├── AgentTerminal.tsx  # Live WebSocket log viewer
│   │   ├── StatusBadge.tsx    # Running / Completed / Failed
│   │   └── IdentityCard.tsx   # Shows loaded applicant info
│   └── hooks/
│       └── useAgentSocket.ts  # WebSocket hook
├── package.json
└── Dockerfile
```

---

## ⚠️ 5. Key Considerations & Optimization

### Context Management (Critical)
- `get_ui_elements()` can return 50 KB+ for complex Workday forms
- **Fix**: Pipe output through `context-mode`'s `ctx_batch_execute` → agent gets ≤300 bytes summary
- llmfit recommends capping context at 8192 tokens on this ARM VM to avoid OOM

### File Upload Handling
- `<input type="file">` bypasses OS picker via PinchTab's file attachment API
- Resume PDF path injected via `APPLICANT_RESUME_PATH` env var

### Token & Step Limits
- `max_steps=20` hard cap in smolagents
- `num_ctx=8192` in Ollama (llmfit-validated for 9 GB RAM envelope)
- If model is slow, drop to `qwen2.5-coder:3b` (23 tok/s, 3.9 GB RAM)

### ARM-Specific Optimizations
- Ollama `OLLAMA_NUM_PARALLEL=1` (avoid OOM with 4 cores)
- `OLLAMA_NUM_THREAD=4` (use all ARM cores)
- PinchTab runs headless Chromium in `--no-sandbox` (container-safe)
- Q4_K_M quantization (best quality/speed on ARM without GPU)

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
open http://localhost:3000
```

**Services after `docker compose up -d`:**

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | React dashboard |
| Backend API | http://localhost:8000 | FastAPI + Swagger docs |
| Ollama | http://localhost:11434 | LLM inference API |
| context-mode | (internal) | MCP context server |

---

## 📁 7. Project Structure

```
smart-apply/
├── docker-compose.yml          ← Single-command launch
├── .env.example               ← Config template
├── ARCHITECTURE.md            ← This file
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
│   └── src/
│
├── context-mode/
│   └── Dockerfile              ← Node.js context MCP server
│
├── ollama/
│   └── entrypoint.sh          ← Auto-pulls qwen2.5-coder:7b
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

*Last updated: 2026-04-07 | Model selected via llmfit v0.9.2 on Oracle Cloud ARM VM*
# ⚡ Smart Apply

> **Autonomous AI job application agent** — Paste a URL, watch it apply.

Powered by `qwen2.5-coder:7b` running locally via Ollama. No cloud API keys required. 100% private.

---

## 🚀 Quick Start (Single Command)

```bash
git clone https://github.com/youruser/smart-apply.git
cd smart-apply

# 1. Copy and edit your identity
cp .env.example .env
# Edit data/identity/identity.csv with your details
# Copy your resume PDF to data/identity/resume.pdf

# 2. Launch everything
docker compose up -d

# First run: downloads qwen2.5-coder:7b (~4.1 GB). Follow progress:
docker logs -f smart-apply-ollama

# 3. Open the dashboard
open http://localhost:3000
```

That's it. Everything — Ollama, the AI model, FastAPI backend, context indexer, and React dashboard — runs in containers.

---

## 🤖 How It Works

```
You paste a job URL
       ↓
Scrapling scrapes the job description (bypasses Cloudflare/LinkedIn)
       ↓
qwen2.5-coder:7b reads the JD + your identity data
       ↓
PinchTab opens headless Chrome → get_ui_elements() reads the form
       ↓
Agent fills each field → clicks Next → repeat until Submit
       ↓
You see every thought and action live in the dashboard
```

### Why these tools?

| Tool | Why |
|------|-----|
| `qwen2.5-coder:7b` | **llmfit** scored it #1 for coding on this ARM VM — 9.5 tok/s, 9 GB RAM |
| Scrapling | Bypasses Cloudflare & LinkedIn anti-bot |
| PinchTab | Token-efficient DOM refs (e5 not `<button class="...">`) |
| context-mode | Prevents DOM floods crashing the 8K context window |
| smolagents | Reliable Python code execution loop with tool calling |

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
| Dashboard | http://localhost:3000 | React UI |
| API | http://localhost:8000 | FastAPI + Swagger |
| Ollama | http://localhost:11434 | LLM inference |

---

## 🔧 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `qwen2.5-coder:7b` | Ollama model to use |
| `LLM_CONTEXT_SIZE` | `8192` | Context window (ARM-optimized) |
| `AGENT_MAX_STEPS` | `20` | Max agent steps before giving up |

See `.env.example` for all options.

---

## 🖥️ Hardware Requirements

This setup was optimized by **llmfit** for:
- **Minimum**: 4 CPU cores, 16 GB RAM, no GPU required
- **Recommended**: 8+ CPU cores, 24 GB RAM
- **Tested on**: Oracle Cloud ARM (Neoverse-N1, 4 cores, 24 GB RAM)

Model can be swapped for faster/smaller options:
- `qwen2.5-coder:3b` — faster (23 tok/s), less capable
- `qwen2.5-coder:14b` — more capable, needs 16+ GB free RAM

---

## 📋 Tracking Progress

See [PROGRESS.md](./PROGRESS.md) for build log and session notes.
See [ARCHITECTURE.md](./ARCHITECTURE.md) for technical deep-dive.

---

*Built with llmfit-selected models • smolagents • PinchTab • Scrapling • context-mode*

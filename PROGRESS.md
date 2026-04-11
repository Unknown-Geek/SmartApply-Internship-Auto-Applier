# 📋 Smart Apply — Build Progress Log

> Track what has been built, what is in progress, and what is next across sessions.

---

## Session 3 — 2026-04-07

### ✅ Completed
- [x] **CI fixes — all checks now passing (exit 0)**
  - `ruff --fix`: sorted all import blocks (I001) across 10 backend files
  - `agent.py`: removed unused `is_transient` variable (F841)
  - `tools.py`: removed unused `resp` assignment on fire-and-forget POST (F841)
  - `.github/workflows/ci.yml`: bumped `actions/checkout` v4→v5, `setup-node` v4→v6
  - `ci.yml`: pinned `node-version` to `"24"` (clears Node.js 20 deprecation warnings)
- [x] **n8n workflow files committed** (`n8n/` directory)
  - `Identity Fetcher.json` — sub-workflow: reads Google Sheet, transforms rows → structured profile JSON
  - `SmartApply - Application Logger.json` — webhook receiver: logs results to Sheets + Telegram
  - `SmartApply - Queue Application.json` — webhook: queues job URLs into Google Sheets
  - `SmartApply - Profile Sync (Trigger).json` — daily poll: pushes profile changes to backend
- [x] **n8n ↔ Backend integration implemented**
  - `data/identity.py`: added `_flatten()` + `ingest_profile_json()` — accepts rich nested profile JSON, flattens to dot-notation, persists as CSV, hot-reloads `_identity`
  - `api/identity.py`: added `POST /profile/ingest/direct` (consumed by Profile Sync workflow) + `GET /profile/schema` (documents expected shape)
  - `api/jobs.py`: added `_notify_n8n_logger()` — fire-and-forget POST to Application Logger webhook on every agent run (success + failure); opt-in via `N8N_LOG_WEBHOOK_URL`
  - `.env.example`: documented `N8N_LOG_WEBHOOK_URL` + `N8N_BACKEND_HOST`

### 📋 To Do (Session 4+)
- [ ] Validate Docker build end-to-end (`docker compose build`)
- [ ] Integration test — apply to a public sample form (e.g. Breezy HR test job)
- [ ] Ink CLI (`npm create ink-app`) for terminal mode
- [ ] Auth layer (API key) for multi-user
- [ ] Rate limiting / job queue (Redis + Celery or FastAPI BackgroundTasks queue)
- [ ] Scrapling anti-bot fine-tuning (LinkedIn specific)
- [ ] PinchTab multi-tab support for parallel applications
- [ ] Frontend: show live tok/s performance metric from Ollama `/api/generate` stream
- [ ] n8n Queue Application → auto-trigger `POST /api/jobs/apply` (close the loop)

---

## Session 2 — 2026-04-07

### ✅ Completed
- [x] **Git initialised** — repo pushed to GitHub, branch `main`
- [x] **Step 1: Bug fixes**
  - PinchTab port corrected 8765→9867 (actual default)
  - Replaced CLI subprocess calls with PinchTab HTTP API + CLI fallback
  - Dockerfile: added xvfb for headless Chromium, fixed PinchTab install
  - supervisord: added xvfb program, fixed `pinchtab server` cmd, priority order
  - jobs.py: proper `ThreadPoolExecutor` for blocking agent, JSON session persistence
  - ws.py: fixed dict-based log serialisation, heartbeat status
- [x] **Step 2: Identity upload API + IdentityPanel UI**
  - `GET /api/identity`, `POST /api/identity/csv`, `POST /api/identity/resume`
  - `IdentityPanel.tsx` — CSV + PDF upload cards with status indicators
  - `vite-env.d.ts` added for ImportMeta type fix
- [x] **Step 3: Dev workflow**
  - `docker-compose.dev.yml` — hot-reload backend (uvicorn --reload) + Vite dev server
  - `Makefile` — up/down/dev/logs/build/health/pull-model/clean/push shortcuts
  - `data/identity/identity.example.csv` — template committed, real CSVs gitignored
  - `data/sessions/.gitkeep` — scaffolds sessions directory
- [x] **Step 4-5: Robustness + health**
  - `agent.py`: retry with backoff (2 retries), transient/permanent error classification
  - `core/config.py`: pydantic-settings centralised configuration
  - `health.py`: deep health — Ollama model status, context-mode, PinchTab version
  - `HealthBar.tsx`: handles new ServiceStatus shape
- [x] **Step 6: CI pipeline**
  - `.github/workflows/ci.yml`: ruff lint, TS type check, Vite build, node syntax, compose validation
  - `pyproject.toml`: ruff linter config


---

## Session 1 — 2026-04-07

### ✅ Completed
- [x] Hardware analysis via **llmfit v0.9.2** — ARM Neoverse-N1, 4c/24GB, no GPU
  - Best model: `qwen3:8b` (32K context, ~4.9 GB Q4, strong instruction following)
- [x] Updated `ARCHITECTURE.md` with llmfit analysis + Docker Compose plan
- [x] Full project scaffold — 30+ files across all 4 services

---

## Known Issues / Gotchas

| Issue | Status | Notes |
|-------|--------|-------|
| PinchTab API endpoint paths | Fixed | Port 9867, HTTP API documented |
| ARM64 headless browser | Fixed | xvfb added to Dockerfile + supervisord |
| Ollama cold-start latency | Known | ~5-10 min on first model pull |
| smolagents blocking event loop | Fixed | Using ThreadPoolExecutor in jobs.py |
| TS lint errors in IDE | Expected | node_modules not on host; compiles fine in Docker |

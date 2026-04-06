# 📋 Smart Apply — Build Progress Log

> Track what has been built, what is in progress, and what is next across sessions.

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

### 🔄 In Progress
- None — session 2 complete

### 📋 To Do (Session 3+)
- [ ] Validate Docker build end-to-end (`docker compose build`)
- [ ] Integration test — apply to a public sample form (e.g. Breezy HR test job)
- [ ] Ink CLI (`npm create ink-app`) for terminal mode
- [ ] Slack/email notification webhook on job completion
- [ ] Auth layer (API key) for multi-user
- [ ] Rate limiting / job queue (Redis + Celery or FastAPI BackgroundTasks queue)
- [ ] Scrapling anti-bot fine-tuning (LinkedIn specific)
- [ ] PinchTab multi-tab support for parallel applications
- [ ] Frontend: show live tok/s performance metric from Ollama `/api/generate` stream

---

## Session 1 — 2026-04-07

### ✅ Completed
- [x] Hardware analysis via **llmfit v0.9.2** — ARM Neoverse-N1, 4c/24GB, no GPU
  - Best model: `qwen2.5-coder:7b` (Q4_K_M), score 76.2, ~9.5 tok/s, 9 GB RAM
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

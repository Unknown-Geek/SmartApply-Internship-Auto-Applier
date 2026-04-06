# backend/Dockerfile
# ARM64-compatible FastAPI backend with smolagents, PinchTab, Scrapling, Supervisor

FROM python:3.11-slim-bookworm

# ─── System dependencies ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    ca-certificates \
    supervisor \
    # Chromium for PinchTab (ARM64 compatible)
    chromium \
    chromium-driver \
    # Scrapling / Playwright stealth deps
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libasound2 \
    # General utilities
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ─── Python dependencies ─────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Install Scrapling browser fingerprints ───────────────────────────────────
RUN scrapling install 2>/dev/null || true

# ─── Install PinchTab ─────────────────────────────────────────────────────────
# Try to install PinchTab. Falls back gracefully if not available on aarch64.
RUN curl -fsSL https://pinchtab.com/install.sh | bash 2>/dev/null \
    && ln -sf ~/.local/bin/pinchtab /usr/local/bin/pinchtab 2>/dev/null \
    || echo "⚠️  PinchTab not available for this arch — using Scrapling-only mode"

# ─── Copy app source ─────────────────────────────────────────────────────────
COPY app/ /app/app/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# ─── Create data directory ────────────────────────────────────────────────────
RUN mkdir -p /app/data/identity /app/data/sessions /app/.chrome_data

# ─── Entrypoint ──────────────────────────────────────────────────────────────
EXPOSE 8000

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

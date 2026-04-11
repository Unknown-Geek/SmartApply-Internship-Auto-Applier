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
    # Xvfb — virtual framebuffer for headless Chromium
    xvfb \
    # Chromium for browser-use / PinchTab (ARM64 native in Debian bookworm)
    chromium \
    chromium-driver \
    # Playwright / Scrapling stealth deps
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
    libx11-xcb1 \
    # General utilities
    build-essential \
    git \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ─── Python dependencies ─────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Install Playwright browsers for browser-use ────────────────────────────
RUN playwright install chromium 2>/dev/null || true

# ─── Install Scrapling browser fingerprints ───────────────────────────────────
RUN scrapling install 2>/dev/null || true

# ─── Install PinchTab (ARM64 linux supported natively) ────────────────────────
RUN curl -fsSL https://pinchtab.com/install.sh | bash 2>/dev/null \
    && (cp ~/.local/bin/pinchtab /usr/local/bin/pinchtab 2>/dev/null || true) \
    && pinchtab --version 2>/dev/null || echo "PinchTab install skipped"

# ─── Copy app source ─────────────────────────────────────────────────────────
COPY app/ /app/app/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# ─── Create data & log directories ───────────────────────────────────────────
RUN mkdir -p /app/data/identity /app/data/sessions /app/.chrome_data \
             /var/log/supervisor

# ─── Chrome/Chromium environment ─────────────────────────────────────────────
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMIUM_FLAGS="--no-sandbox --disable-dev-shm-usage --headless=new"
ENV DISPLAY=:99

EXPOSE 8000

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

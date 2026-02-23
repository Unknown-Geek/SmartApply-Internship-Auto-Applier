#!/bin/bash
# =============================================================================
# SmartApply — OCI Ubuntu VM Setup Script
# =============================================================================
# Sets up Python, Playwright, and all dependencies.
#
# Usage:
#   chmod +x setup.sh && ./setup.sh
# =============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() { echo -e "\n${BLUE}==>${NC} ${GREEN}$1${NC}"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}WARNING:${NC} $1"; }

# ---- System packages ----
print_step "Updating system packages..."
sudo apt-get update -y && sudo apt-get upgrade -y
sudo apt-get install -y build-essential curl wget git

# ---- Python 3.11 ----
print_step "Installing Python 3.11..."
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update -y
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
print_success "Python $(python3.11 --version) installed"

# ---- Virtual environment ----
print_step "Creating virtual environment..."
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
print_success "Virtual environment ready"

# ---- Python dependencies ----
print_step "Installing Python dependencies..."
pip install -r requirements.txt
print_success "Dependencies installed"

# ---- Playwright ----
print_step "Installing Playwright system dependencies..."
sudo apt-get install -y \
    libwoff1 libopus0 libwebp7 libwebpdemux2 libenchant-2-2 \
    libgudev-1.0-0 libsecret-1-0 libhyphen0 libgdk-pixbuf2.0-0 \
    libegl1 libnotify4 libxslt1.1 libevent-2.1-7 libgles2 \
    libxcomposite1 libatk1.0-0 libatk-bridge2.0-0 libepoxy0 \
    libgtk-3-0 libharfbuzz-icu0 libgstreamer-gl1.0-0 \
    libgstreamer-plugins-bad1.0-0 gstreamer1.0-plugins-good \
    gstreamer1.0-libav libavif15 libxkbcommon0 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 \
    libxdamage1 fonts-liberation fonts-noto-color-emoji xvfb

playwright install chromium --with-deps
print_success "Playwright + Chromium installed"

# ---- Environment file ----
print_step "Setting up environment..."
if [ ! -f .env ]; then
    cp .env.template .env
    print_warning ".env created from template — edit it with your API keys!"
else
    print_success ".env already exists"
fi

# ---- Verify ----
print_step "Verifying installation..."
python -c "import fastapi; print(f'  FastAPI: {fastapi.__version__}')"
python -c "import openai; print(f'  OpenAI SDK: {openai.__version__}')"
python -c "import playwright; print('  Playwright: installed')"
python -c "import telegram; print(f'  Telegram Bot: {telegram.__version__}')"

echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Edit ${YELLOW}.env${NC} with your CEREBRAS_API_KEY"
echo -e "  2. (Optional) Add TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID"
echo -e "  3. Activate: ${BLUE}source venv/bin/activate${NC}"
echo -e "  4. Start: ${BLUE}./start.sh${NC}"
echo ""

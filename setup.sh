#!/bin/bash
# =============================================================================
# SmartApply Web Agent - OCI Ubuntu VM Setup Script
# =============================================================================
# This script sets up a complete Python environment for running the web agent
# on an OCI (Oracle Cloud Infrastructure) Ubuntu VM.
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
#
# Requirements:
#   - Ubuntu 20.04+ (OCI VM)
#   - sudo privileges
# =============================================================================

set -e  # Exit immediately if a command exits with a non-zero status

# -----------------------------------------------------------------------------
# Color codes for output formatting
# -----------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
print_step() {
    echo -e "\n${BLUE}==>${NC} ${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

print_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# =============================================================================
# STEP 1: System Update and Essential Packages
# =============================================================================
print_step "Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

print_step "Installing essential build tools..."
sudo apt-get install -y \
    build-essential \
    curl \
    wget \
    git \
    software-properties-common

# =============================================================================
# STEP 2: Python 3.11+ Installation
# =============================================================================
print_step "Installing Python 3.11..."

# Add deadsnakes PPA for Python 3.11 (if not on Ubuntu 22.04+)
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update -y

# Install Python 3.11 and required packages
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip

# Update alternatives to use Python 3.11 as default python3
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

print_success "Python $(python3.11 --version) installed"

# =============================================================================
# STEP 3: Virtual Environment Setup
# =============================================================================
print_step "Creating Python virtual environment..."

# Create virtual environment using venv
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

print_success "Virtual environment created and activated"

# Upgrade pip inside venv
print_step "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# =============================================================================
# STEP 4: Install Python Dependencies
# =============================================================================
print_step "Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt

print_success "Python dependencies installed"

# =============================================================================
# STEP 5: Playwright System Dependencies (for headless browsers)
# =============================================================================
print_step "Installing Playwright system dependencies..."

# Install system dependencies required by Playwright browsers
# This handles libs needed for Chromium, Firefox, and WebKit on Ubuntu
sudo apt-get install -y \
    libwoff1 \
    libopus0 \
    libwebp7 \
    libwebpdemux2 \
    libenchant-2-2 \
    libgudev-1.0-0 \
    libsecret-1-0 \
    libhyphen0 \
    libgdk-pixbuf2.0-0 \
    libegl1 \
    libnotify4 \
    libxslt1.1 \
    libevent-2.1-7 \
    libgles2 \
    libxcomposite1 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libepoxy0 \
    libgtk-3-0 \
    libharfbuzz-icu0 \
    libgstreamer-gl1.0-0 \
    libgstreamer-plugins-bad1.0-0 \
    gstreamer1.0-plugins-good \
    gstreamer1.0-libav \
    libavif15 \
    libxkbcommon0 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libxdamage1 \
    fonts-liberation \
    fonts-noto-color-emoji \
    xvfb

print_success "Playwright system dependencies installed"

# =============================================================================
# STEP 6: Install Playwright Browsers
# =============================================================================
print_step "Installing Playwright browsers (Chromium)..."

# Install Playwright browsers with system dependencies
# Using --with-deps ensures all required system libs are installed
playwright install chromium --with-deps

print_success "Playwright Chromium browser installed"

# =============================================================================
# STEP 7: Environment Configuration
# =============================================================================
print_step "Setting up environment configuration..."

# Copy .env.template to .env if it doesn't exist
if [ ! -f .env ]; then
    cp .env.template .env
    print_warning ".env file created from template. Please edit it with your API keys!"
else
    print_success ".env file already exists"
fi

# =============================================================================
# STEP 8: Verification
# =============================================================================
print_step "Verifying installation..."

echo -e "\n${GREEN}Installed versions:${NC}"
echo "  Python: $(python --version)"
echo "  Pip: $(pip --version)"

# Verify key packages
python -c "import fastapi; print(f'  FastAPI: {fastapi.__version__}')"
python -c "import playwright; print(f'  Playwright: installed')"
python -c "import langchain_google_genai; print(f'  LangChain Google GenAI: installed')"

# =============================================================================
# Setup Complete!
# =============================================================================
echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Edit ${YELLOW}.env${NC} and add your GOOGLE_API_KEY"
echo -e "  2. Activate the virtual environment:"
echo -e "     ${BLUE}source venv/bin/activate${NC}"
echo -e "  3. Start the server:"
echo -e "     ${BLUE}uvicorn app.main:app --host 0.0.0.0 --port 8000${NC}"
echo ""
echo -e "For development (with auto-reload):"
echo -e "     ${BLUE}uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload${NC}"
echo ""

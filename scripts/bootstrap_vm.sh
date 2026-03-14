#!/usr/bin/env bash
set -euo pipefail

# SmartApply VM bootstrap for Azure Ubuntu/Debian.
# Installs Ollama, Scrapling (MCP), PinchTab, and n8n-claw.

MODEL="${MODEL:-qwen2.5-coder:7b}"
N8N_CLAW_DIR="${N8N_CLAW_DIR:-$HOME/n8n-claw}"
SCRAPLING_ENV="${SCRAPLING_ENV:-$HOME/scrapling-env}"
OLLAMA_SERVICE_FILE="/etc/systemd/system/ollama.service"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

install_ollama() {
  echo "[1/7] Installing Ollama"
  curl -fsSL https://ollama.com/install.sh | sh

  # Ensure service file exposes Ollama to Docker containers.
  if sudo test -f "$OLLAMA_SERVICE_FILE"; then
    if ! sudo grep -q 'OLLAMA_HOST=0.0.0.0' "$OLLAMA_SERVICE_FILE"; then
      echo "Configuring Ollama systemd service binding"
      sudo sed -i '/^\[Service\]/a Environment="OLLAMA_HOST=0.0.0.0"' "$OLLAMA_SERVICE_FILE"
    fi
  else
    echo "Expected Ollama service file not found: $OLLAMA_SERVICE_FILE" >&2
    exit 1
  fi

  sudo systemctl daemon-reload
  sudo systemctl restart ollama
  sudo systemctl enable ollama

  echo "Waiting for Ollama to become healthy..."
  for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done

  echo "Pulling model: $MODEL"
  ollama pull "$MODEL"
}

install_scrapling() {
  echo "[2/7] Installing Scrapling MCP environment"
  sudo apt update
  sudo apt install -y python3-venv python3-pip

  if [ ! -d "$SCRAPLING_ENV" ]; then
    python3 -m venv "$SCRAPLING_ENV"
  fi

  # shellcheck disable=SC1091
  source "$SCRAPLING_ENV/bin/activate"
  pip install --upgrade pip
  pip install "scrapling[ai]"
  scrapling install
  deactivate
}

install_pinchtab() {
  echo "[3/7] Installing PinchTab"
  curl -fsSL https://pinchtab.com/install.sh | bash

  if command -v pinchtab >/dev/null 2>&1; then
    pinchtab daemon install || true
    pinchtab daemon || true
  else
    echo "PinchTab was not found on PATH after install." >&2
    exit 1
  fi
}

install_n8n_claw() {
  echo "[4/7] Cloning n8n-claw"
  if [ ! -d "$N8N_CLAW_DIR/.git" ]; then
    git clone https://github.com/freddy-schuetz/n8n-claw.git "$N8N_CLAW_DIR"
  else
    echo "n8n-claw already exists at $N8N_CLAW_DIR, pulling latest changes"
    git -C "$N8N_CLAW_DIR" pull --ff-only
  fi

  echo "[5/7] Running n8n-claw setup script"
  echo "The setup is interactive. Use a dummy Anthropic key if you are switching to Ollama later."
  (cd "$N8N_CLAW_DIR" && ./setup.sh)
}

write_linux_host_hint() {
  echo "[6/7] Writing Linux Docker host alias hint"
  cat <<'EOF'

If Ollama cannot be reached from Docker containers via host.docker.internal on Linux,
add this to n8n-claw docker compose service for n8n:

  extra_hosts:
    - "host.docker.internal:host-gateway"

Then restart stack:
  docker compose up -d
EOF
}

run_validation() {
  echo "[7/7] Running post-install checks"
  "$PWD/scripts/validate_stack.sh" || true
}

main() {
  require_cmd curl
  require_cmd git

  install_ollama
  install_scrapling
  install_pinchtab
  install_n8n_claw
  write_linux_host_hint
  run_validation

  cat <<'EOF'

Bootstrap completed.
Next steps in n8n UI:
1) Replace Anthropic chat model with Ollama Chat Model (qwen2.5-coder:7b).
2) Register MCP servers for Scrapling and PinchTab.
3) Import workflows/Automated_Job_Apply_Loop.template.json and configure credentials.
EOF
}

main "$@"

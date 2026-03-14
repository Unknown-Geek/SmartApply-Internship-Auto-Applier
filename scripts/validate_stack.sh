#!/usr/bin/env bash
set -euo pipefail

echo "Validating SmartApply local stack..."

check_url() {
  local url="$1"
  local name="$2"
  if curl -fsS "$url" >/dev/null 2>&1; then
    echo "[OK] $name"
  else
    echo "[WARN] $name is not reachable at $url"
  fi
}

check_cmd() {
  local cmd="$1"
  local name="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "[OK] $name"
  else
    echo "[WARN] Missing command: $cmd"
  fi
}

check_cmd ollama "Ollama CLI"
check_cmd pinchtab "PinchTab CLI"

check_url http://127.0.0.1:11434/api/tags "Ollama API"
check_url http://127.0.0.1:9867/health "PinchTab API"

if command -v ollama >/dev/null 2>&1; then
  if ollama list | grep -q "qwen2.5-coder:7b"; then
    echo "[OK] qwen2.5-coder:7b present"
  else
    echo "[WARN] qwen2.5-coder:7b not found in local Ollama"
  fi
fi

if [ -d "$HOME/scrapling-env" ] && [ -x "$HOME/scrapling-env/bin/python" ]; then
  echo "[OK] Scrapling virtualenv present"
else
  echo "[WARN] Scrapling virtualenv missing at $HOME/scrapling-env"
fi

if [ -d "$HOME/n8n-claw" ]; then
  echo "[OK] n8n-claw directory exists"
else
  echo "[WARN] n8n-claw directory not found at $HOME/n8n-claw"
fi

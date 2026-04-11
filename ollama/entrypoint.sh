#!/bin/bash
# ollama/entrypoint.sh
# Starts Ollama server and auto-pulls qwen3:8b on first boot.
# Model is ~4.9 GB — only downloaded once, cached in ollama_data volume.

set -e

MODEL="${LLM_MODEL:-qwen3:8b}"

echo "🚀 [Ollama] Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!

# Wait for the API to be ready
echo "⏳ [Ollama] Waiting for API to be ready..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
  sleep 2
done

echo "✅ [Ollama] API is ready."

# Check if model is already pulled
if ollama list | grep -q "${MODEL}"; then
  echo "✅ [Ollama] Model '${MODEL}' already installed — skipping pull."
else
  echo "📥 [Ollama] Pulling model '${MODEL}' (first-time setup, ~4.9 GB)..."
  ollama pull "${MODEL}"
  echo "✅ [Ollama] Model '${MODEL}' pulled successfully."
fi

echo "🎉 [Ollama] Ready for inference. Model: ${MODEL}"

# Keep the process alive (wait for ollama serve)
wait $OLLAMA_PID

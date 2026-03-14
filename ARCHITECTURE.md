# ARCHITECTURE

Last Updated: 2026-03-14

## Current Repository Structure

- README.md
- ARCHITECTURE.md
- PROJECT_IDEA.md
- docs/
  - DEPLOYMENT_RUNBOOK.md
- .githooks/
  - post-commit
- scripts/
  - bootstrap_vm.sh
  - validate_stack.sh
  - git_autopush.sh
- workflows/
  - Automated_Job_Apply_Loop.template.json

## Runtime Architecture (Target on Azure VM)

1. Local LLM Layer
- Ollama systemd service bound on 0.0.0.0:11434
- Model: qwen2.5-coder:7b

2. Automation Layer
- PinchTab daemon for browser control
- Scrapling MCP server via Python virtual environment

3. Orchestration Layer
- n8n-claw (Docker-based) as workflow and agent orchestrator
- n8n AI Agent node uses Ollama Chat Model
- n8n MCP Tool nodes call Scrapling + PinchTab

4. Data/State Layer
- Google Sheets for internship leads and identity data
- Telegram for operator notifications

## Integration Notes

- Linux Docker to host Ollama may require:
  - host.docker.internal mapping to host-gateway in docker compose.
- n8n workflow import template provided in workflows directory.
- MCP server registration in n8n is still UI-driven.

## Codebase Maintenance Rules

- Keep this file updated after each major run.
- Reflect real file tree and runtime architecture deltas.

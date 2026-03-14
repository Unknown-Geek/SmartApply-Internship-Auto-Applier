# SmartApply-Internship-Auto-Applier

Fully local AI-agent automation stack for internship applications on Azure VM using:

- Ollama + qwen2.5-coder:7b (local LLM)
- n8n-claw (orchestration)
- Scrapling MCP (web extraction)
- PinchTab MCP (browser automation)
- Google Sheets + Telegram (ops integrations)

## What This Repository Contains

- `scripts/bootstrap_vm.sh`: End-to-end VM bootstrap for Ollama, Scrapling, PinchTab, and n8n-claw.
- `scripts/validate_stack.sh`: Post-install checks.
- `scripts/git_autopush.sh`: Commit + push helper.
- `workflows/Automated_Job_Apply_Loop.template.json`: n8n import template for the Smart Apply loop.
- `docs/DEPLOYMENT_RUNBOOK.md`: Manual and automated setup playbook.
- `ARCHITECTURE.md`: Current codebase and runtime architecture state.
- `PROJECT_IDEA.md`: Detailed implementation intent and constraints.

## Quick Start (Azure VM)

```bash
git clone <your-repo-url>
cd SmartApply-Internship-Auto-Applier
chmod +x scripts/*.sh .githooks/post-commit
./scripts/bootstrap_vm.sh
```

Then continue with the n8n steps in `docs/DEPLOYMENT_RUNBOOK.md`.

## Important Notes

1. The bootstrap script automates system installation and local tooling.
2. n8n node rewiring and MCP registration are still done in UI for reliability and credential safety.
3. Linux Docker may need `host.docker.internal:host-gateway` mapping if Ollama is not reachable from containers.

## Auto Push Options

Manual per run:

```bash
./scripts/git_autopush.sh "chore: update stack"
```

Automatic on each local commit:

```bash
git config core.hooksPath .githooks
```

## Required Documentation Maintenance

After each run, update:

- `ARCHITECTURE.md`
- `PROJECT_IDEA.md`

These files are treated as the source-of-truth state of the project.

## Model Choice

Default model is `qwen2.5-coder:7b`, selected for local reasoning and structured output suitability.

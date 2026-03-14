# Deployment Runbook

## 1) Bootstrap the VM

Run on Azure VM:

```bash
cd ~/SmartApply-Internship-Auto-Applier
chmod +x scripts/*.sh
./scripts/bootstrap_vm.sh
```

## 2) Validate Services

```bash
./scripts/validate_stack.sh
```

Expected healthy endpoints:
- Ollama API: http://127.0.0.1:11434/api/tags
- PinchTab API: http://127.0.0.1:9867/health

## 3) Configure n8n-claw to use Ollama

1. Open n8n: http://<VM_IP>:5678
2. Open workflow: "🤖 n8n-claw Agent"
3. Remove Anthropic node from language model path.
4. Add Ollama Chat Model node.
5. Set model to qwen2.5-coder:7b.
6. Set base URL to one of:
   - http://host.docker.internal:11434
   - If unreachable on Linux, add docker compose extra host mapping:
     - host.docker.internal:host-gateway

## 4) Register MCP Servers in n8n

Open Settings > MCP Servers and add:

1. Scrapling
- Name: Scrapling
- Type: command
- Command: /home/<username>/scrapling-env/bin/python
- Args: ["-m", "scrapling.mcp_server"]

2. PinchTab
- Name: PinchTab
- Type: command
- Command: /home/<username>/.local/bin/pinchtab
- Args: ["mcp"]

## 5) Import the SmartApply workflow template

1. In n8n, import:
   - workflows/Automated_Job_Apply_Loop.template.json
2. Configure credentials for:
   - Google Sheets
   - Telegram
   - Ollama
3. Configure environment values for:
   - INTERNSHIP_SHEET_ID
   - IDENTITY_SHEET_ID
   - TELEGRAM_CHAT_ID

## 6) Smoke Test

1. Trigger workflow manually with one test lead.
2. Confirm AI agent response contains strict JSON fields:
   - status
   - company
   - role
   - notes
3. Confirm Telegram notification and Google Sheet status update.

## 7) Monitoring

Use VM shell:

```bash
ollama logs
```

Additional logs:

```bash
docker logs n8n-claw --tail 200
```

## 8) Git Versioning

Manual autopush command:

```bash
./scripts/git_autopush.sh "chore: update smartapply pipeline"
```

Optional hook-based auto-push setup:

```bash
git config core.hooksPath .githooks
chmod +x .githooks/post-commit
```

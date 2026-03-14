# PROJECT_IDEA

Last Updated: 2026-03-14

## Project Name
SmartApply Internship Auto Applier

## Vision
Build a fully local, autonomous internship application agent on an Azure VM using Ollama + n8n + MCP tools (Scrapling and PinchTab), minimizing recurring API costs and keeping sensitive data on-host.

## Core Goals

1. Replace cloud LLM dependency in n8n-claw with local Ollama model.
2. Use MCP tooling for robust web extraction and browser interaction.
3. Automate a recurring job-application loop from a leads sheet.
4. Notify operator via Telegram and write back application status.
5. Maintain auditable repo state with repeatable scripts and git push flow.

## Functional Scope

- VM bootstrap automation for all core components.
- n8n workflow template for schedule-driven application loop.
- Setup and validation scripts.
- Operational runbook for manual n8n configuration steps.

## Constraints and Risks

- Some n8n actions are interactive/UI-based and cannot be fully scripted reliably without full API credential material.
- Automated form submission can trigger anti-bot systems or legal/compliance constraints depending on job platform terms.
- Local 7B model latency on 4 vCPU VM may be significant.

## Success Criteria

- Ollama serves qwen2.5-coder:7b locally.
- PinchTab and Scrapling MCP endpoints are callable.
- n8n agent uses Ollama node instead of Anthropic node.
- Workflow can read pending leads, apply, notify, and mark status as applied.

## Planned Enhancements

- Add dry-run mode for safe simulation before real submission.
- Add confidence gate + human approval step.
- Add execution logs archive to cloud storage.
- Add CI linting for scripts and workflow schema checks.

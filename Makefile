.PHONY: up down dev logs pull-model ps clean help

## ── Prod ─────────────────────────────────────────────────────────────────────
up: ## Start all services (production)
	docker compose up -d

down: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose restart

## ── Dev ──────────────────────────────────────────────────────────────────────
dev: ## Start with hot-reload (development mode)
	docker compose -f docker-compose.dev.yml up

dev-down: ## Stop dev services
	docker compose -f docker-compose.dev.yml down

## ── Logs ─────────────────────────────────────────────────────────────────────
logs: ## Follow all service logs
	docker compose logs -f

logs-backend: ## Follow backend logs only
	docker compose logs -f backend

logs-ollama: ## Follow Ollama (model pull progress)
	docker compose logs -f ollama

## ── Model ─────────────────────────────────────────────────────────────────────
pull-model: ## Manually trigger model pull inside Ollama container
	docker exec smart-apply-ollama ollama pull qwen3:8b

list-models: ## List models installed in Ollama
	docker exec smart-apply-ollama ollama list

## ── Build ─────────────────────────────────────────────────────────────────────
build: ## Rebuild all Docker images
	docker compose build --no-cache

build-backend: ## Rebuild backend image only
	docker compose build --no-cache backend

build-frontend: ## Rebuild frontend image only
	docker compose build --no-cache frontend

## ── Status ────────────────────────────────────────────────────────────────────
ps: ## Show running containers
	docker compose ps

health: ## Check health of all services
	@curl -sf http://localhost:8000/api/health | python3 -m json.tool || echo "Backend not ready"

## ── Data ──────────────────────────────────────────────────────────────────────
setup-data: ## Create data directories and copy example identity
	@mkdir -p data/identity
	@if [ ! -f data/identity/identity.csv ]; then \
		cp data/identity/identity.example.csv data/identity/identity.csv; \
		echo "✅ Created data/identity/identity.csv — edit it with your details"; \
	fi

## ── Cleanup ───────────────────────────────────────────────────────────────────
clean: ## Remove containers and volumes (WARNING: deletes downloaded model!)
	docker compose down -v

clean-sessions: ## Clear agent session logs
	@rm -rf data/sessions/*.json && echo "✅ Sessions cleared"

## ── Git ───────────────────────────────────────────────────────────────────────
push: ## Add, commit with message, and push (usage: make push MSG="your message")
	git add -A && git commit -m "$(MSG)" && git push

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help

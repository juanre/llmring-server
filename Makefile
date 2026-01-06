# LLMRing Server Development & Docker Management
#
# Goals:
# - Local dev runs without Docker (fast iteration, uses local Postgres/Redis)
# - Docker is reserved for production-like testing
#
# Port defaults are chosen to avoid BeadHub conflicts (BeadHub uses 8000/9000/5173/5432/6379).

.PHONY: help dev dev-stop docker docker-stop docker-rebuild logs status health clean prune

# Optional env file (can be overridden: `make ENV_FILE=.env.dev docker`)
ENV_FILE ?= .env.dev

ifneq (,$(wildcard $(ENV_FILE)))
include $(ENV_FILE)
export
endif

# Defaults (override via env or ENV_FILE)
LLMRING_DEV_PORT ?= 9101
LLMRING_HTTP_PORT ?= 9100

LLMRING_DATABASE_URL ?= postgresql://localhost/llmring_dev
LLMRING_DATABASE_SCHEMA ?= llmring
LLMRING_REDIS_URL ?= redis://localhost:6379/0

DOCKER_PROJECT ?= llmring-server-docker

help:
	@echo "LLMRing Server Commands:"
	@echo ""
	@echo "  Local Development (no Docker):"
	@echo "    make dev          - Run server with auto-reload on port $(LLMRING_DEV_PORT)"
	@echo "    make dev-stop     - Kill local dev server on port $(LLMRING_DEV_PORT)"
	@echo ""
	@echo "  Production-like Docker stack:"
	@echo "    make docker       - Start server+db+redis in Docker on port $(LLMRING_HTTP_PORT)"
	@echo "    make docker-stop  - Stop Docker services"
	@echo "    make docker-rebuild - Rebuild and restart server container"
	@echo ""
	@echo "  Utilities:"
	@echo "    make health       - Check /health for docker stack"
	@echo "    make logs         - Follow docker logs"
	@echo "    make status       - Show docker service status"
	@echo ""
	@echo "  Port Allocation:"
	@echo "    dev:    server=$(LLMRING_DEV_PORT) (local postgres/redis)"
	@echo "    docker: server=$(LLMRING_HTTP_PORT) (db/redis not exposed)"

dev:
	@echo "Starting llmring-server (dev) on port $(LLMRING_DEV_PORT)..."
	@echo "  API:    http://localhost:$(LLMRING_DEV_PORT)"
	@echo "  Docs:   http://localhost:$(LLMRING_DEV_PORT)/docs"
	@echo "  Health: http://localhost:$(LLMRING_DEV_PORT)/health"
	@echo "  DB:     $(LLMRING_DATABASE_URL)"
	@echo "  Redis:  $(LLMRING_REDIS_URL) (optional)"
	@echo ""
	LLMRING_DATABASE_URL="$(LLMRING_DATABASE_URL)" \
	LLMRING_DATABASE_SCHEMA="$(LLMRING_DATABASE_SCHEMA)" \
	LLMRING_REDIS_URL="$(LLMRING_REDIS_URL)" \
	uv run llmring-server db create --env dev || true
	LLMRING_DATABASE_URL="$(LLMRING_DATABASE_URL)" \
	LLMRING_DATABASE_SCHEMA="$(LLMRING_DATABASE_SCHEMA)" \
	LLMRING_REDIS_URL="$(LLMRING_REDIS_URL)" \
	uv run llmring-server db migrate --env dev
	LLMRING_DATABASE_URL="$(LLMRING_DATABASE_URL)" \
	LLMRING_DATABASE_SCHEMA="$(LLMRING_DATABASE_SCHEMA)" \
	LLMRING_REDIS_URL="$(LLMRING_REDIS_URL)" \
	exec uv run llmring-server serve --env dev --reload --port $(LLMRING_DEV_PORT)

dev-stop:
	@echo "Stopping dev server on port $(LLMRING_DEV_PORT)..."
	-@lsof -ti :$(LLMRING_DEV_PORT) | xargs kill 2>/dev/null || true
	@echo "Done."

docker:
	@LLMRING_HTTP_PORT="$(LLMRING_HTTP_PORT)" docker compose -p $(DOCKER_PROJECT) up -d --build
	@echo ""
	@echo "Docker services running:"
	@echo "  Server:  http://localhost:$(LLMRING_HTTP_PORT)"
	@echo "  Health:  http://localhost:$(LLMRING_HTTP_PORT)/health"
	@$(MAKE) health LLMRING_HTTP_PORT=$(LLMRING_HTTP_PORT)

docker-stop:
	docker compose -p $(DOCKER_PROJECT) down

docker-rebuild:
	docker compose -p $(DOCKER_PROJECT) build server
	docker compose -p $(DOCKER_PROJECT) up -d server
	@$(MAKE) health LLMRING_HTTP_PORT=$(LLMRING_HTTP_PORT)

health:
	@echo ""
	@echo "Checking health..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if curl -sf http://localhost:$(LLMRING_HTTP_PORT)/health > /dev/null 2>&1; then \
			curl -s http://localhost:$(LLMRING_HTTP_PORT)/health; echo ""; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Health check failed after 10s"; \
	exit 1

logs:
	docker compose -p $(DOCKER_PROJECT) logs -f

status:
	@docker compose -p $(DOCKER_PROJECT) ps 2>/dev/null || echo "(not running)"

clean:
	docker compose -p $(DOCKER_PROJECT) down -v --remove-orphans

prune:
	@echo "Removing dangling images and unused volumes..."
	-docker image prune -f
	-docker volume prune -f

.PHONY: help build run stop clean install dev test

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	pip install -r requirements.txt

dev: ## Run in development mode
	uvicorn app:app --host 0.0.0.0 --port 8000 --reload

build: ## Build Docker image
	docker build -t aws-ecs-recommendations .

run: ## Run with Docker
	docker run -d -p 8000:8000 --name aws-ecs-recommendations --env-file .env aws-ecs-recommendations

compose-up: ## Start with docker-compose
	docker-compose up -d

compose-down: ## Stop docker-compose
	docker-compose down

stop: ## Stop Docker container
	docker stop aws-ecs-recommendations || true
	docker rm aws-ecs-recommendations || true

clean: ## Clean up Docker resources
	docker stop aws-ecs-recommendations || true
	docker rm aws-ecs-recommendations || true
	docker rmi aws-ecs-recommendations || true

logs: ## Show Docker logs
	docker logs -f aws-ecs-recommendations

test: ## Run tests (placeholder)
	@echo "No tests configured yet"

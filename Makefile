.PHONY: help install backend frontend test eval lint build

help: ## List the commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

install: ## Install dependencies, the git hooks, and backend/.env if it is missing
	cd backend && uv sync
	cd frontend && npm install
	prek install
	@test -f backend/.env || (cp backend/.env.example backend/.env && echo "Created backend/.env: fill in DATABASE_URL and OPENAI_API_KEY")

backend: ## Run the API on http://localhost:8000
	cd backend && uv run --env-file .env fastapi dev app/main.py

frontend: ## Run the app on http://localhost:5173
	cd frontend && npm run dev

test: ## Run the backend's unit tests (no database or API key needed)
	cd backend && uv run pytest --ignore tests/test_agent.py

eval: ## Score the agent with DeepEval (needs the database and OPENAI_API_KEY)
	cd backend && uv run --env-file .env deepeval test run tests/test_agent.py

lint: ## Run every prek hook on all tracked files
	prek run --all-files

build: ## Type-check and build the frontend
	cd frontend && npm run build

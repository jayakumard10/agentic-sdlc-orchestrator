.PHONY: up down build logs test test-orchestrator test-target-app coverage clean

up: ## Start the full stack (postgres, target_app, orchestrator runs all 3 demos, exits)
	docker compose up --build

down: ## Stop and remove all containers, networks (keeps volumes)
	docker compose down

build: ## Build both images without starting anything
	docker compose build

logs: ## Follow orchestrator container output
	docker compose logs -f orchestrator

demo-greenfield: ## Run only the greenfield scenario
	docker compose run --rm orchestrator python scenarios/run_greenfield.py

demo-brownfield: ## Run only the brownfield scenario
	docker compose run --rm orchestrator python scenarios/run_brownfield.py

demo-ambiguous: ## Run only the ambiguous scenario
	docker compose run --rm orchestrator python scenarios/run_ambiguous.py

test: test-orchestrator test-target-app ## Run both test suites

test-orchestrator: ## Run the orchestrator's own test suite
	cd orchestrator && python -m pytest tests/ -v

test-target-app: ## Run the target app's test suite
	cd target_app && python -m pytest -v

coverage: ## Regenerate both coverage reports
	cd orchestrator && python -m pytest tests/ --cov=. --cov-report=term-missing
	cd target_app && python -m pytest --cov=app --cov-report=term-missing

clean: ## Remove containers, networks, and volumes (destructive - resets postgres data)
	docker compose down -v

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

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
	@echo up                 Start the full stack (build + run all 3 demos, then exit)
	@echo down                Stop and remove all containers, networks (keeps volumes)
	@echo build                Build both images without starting anything
	@echo logs                Follow orchestrator container output
	@echo demo-greenfield       Run only the greenfield scenario
	@echo demo-brownfield       Run only the brownfield scenario
	@echo demo-ambiguous        Run only the ambiguous scenario
	@echo test                Run both test suites
	@echo test-orchestrator     Run the orchestrator's own test suite
	@echo test-target-app       Run the target app's test suite
	@echo coverage             Regenerate both coverage reports
	@echo clean                Remove containers, networks, and volumes (destructive)

.PHONY : help
help: ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "}; /^[a-zA-Z_-]+:.*?## .*$$/ {printf "\033[36m%-20s\033[0m %s

.PHONY: check
check: ## Run code quality tools.
	@echo "🚀 Linting code: Running black"
	@black --check lambda_function/*

	@echo "🚀 Linting code: Running flake8"
	@flake8 lambda_function/* --max-line-length=100

.PHONY: test
test: ## Test the code with pytest and open the coverage report in the browser.
	@echo "🚀 Testing code: Running pytest"
	@pytest -s tests --cov=lambda_function/ --cov-report=html --log-cli-level=INFO
	@echo "🚀 Opening coverage report in browser"
	@(xdg-open htmlcov/index.html &)

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
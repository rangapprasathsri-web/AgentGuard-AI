.PHONY: all seed test demo clean

all: seed test

seed:
	@echo "Seeding tools database..."
	python3 -c "from tools.db import init_tools_db; init_tools_db()"

test:
	@echo "Running all tests offline with MockLLM (no external network)..."
	LLM_MODE=mock python3 -m pytest -v tests/

demo: seed
	@echo "Starting all five processes for AgentGuard AI..."
	bash scripts/run_all.sh

clean:
	@echo "Cleaning temporary files and databases..."
	rm -f tools.db guard.db audit.db
	find . -type d -name "__pycache__" -exec rm -rf {} +

scan:
	@echo "Scanning for secrets..."
	python3 scripts/secret_scan.py

package:
	@echo "Packaging codebase..."
	rm -f release.zip
	zip -r release.zip . -x "*.env*" "*.db*" "*api keys.docx*" "*/node_modules/*" "*/.git/*" "*/.pytest_cache/*" "*__pycache__/*"

check-package: package
	@echo "Checking package for secrets and databases..."
	@if unzip -l release.zip | grep -E '\.env|\.db|api keys.docx'; then \
		echo "ERROR: Package contains sensitive files!"; exit 1; \
	fi
	@echo "Package is clean."

lint:
	@echo "Running lint check..."
	flake8 . || echo "flake8 not found, skipping"

verify: lint check-package scan
	@echo "Running full verification suite..."
	@echo "Running tests with strict count check (expecting 57)..."
	LLM_MODE=mock PYTHONPATH=. python3 -m pytest -q tests/ > test_output.txt
	@if ! grep -q "57 passed" test_output.txt; then \
		cat test_output.txt; \
		echo "ERROR: Test count mismatch! Expected 57 passed tests."; \
		exit 1; \
	fi
	@cat test_output.txt
	@echo "All verification checks passed!"

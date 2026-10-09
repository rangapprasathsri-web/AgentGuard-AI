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


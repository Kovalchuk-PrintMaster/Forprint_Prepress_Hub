.PHONY: help env test bootstrap-check governance-check status

PYTHON ?= .venv_prepress_hub/bin/python

help:
	@echo "ForPrint Prepress Hub operator map"
	@echo "  make env              - create/update dedicated Python environment"
	@echo "  make test             - run repository tests"
	@echo "  make bootstrap-check  - validate bootstrap foundation"
	@echo "  make governance-check - run current local governance checks"
	@echo "  make status           - show Git and module status"

env:
	python3 -m venv .venv_prepress_hub
	.venv_prepress_hub/bin/python -m pip install --upgrade pip
	.venv_prepress_hub/bin/python -m pip install -e '.[dev]'

test:
	$(PYTHON) -m pytest -q

bootstrap-check:
	$(PYTHON) scripts/validation/check_bootstrap_foundation.py

governance-check: bootstrap-check test
	@git diff --check
	@echo "PREPRESS_HUB_GOVERNANCE_CHECK=PASS"

status:
	@git status --short
	@echo "---"
	@cat coordination/status/current_status.yaml

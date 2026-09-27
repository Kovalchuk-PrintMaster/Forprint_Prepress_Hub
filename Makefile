.PHONY: help env test bootstrap-check governance-check status graphic-design-lab-planning-check graphic-design-lab-contracts-check

PYTHON ?= .venv_prepress_hub/bin/python

help:
	@echo "ForPrint Prepress Hub operator map"
	@echo "  make env              - create/update dedicated Python environment"
	@echo "  make test             - run repository tests"
	@echo "  make bootstrap-check  - validate bootstrap foundation"
	@echo "  make governance-check - run current local governance checks"
	@echo "  make status           - show Git and module status"
	@echo "  make graphic-design-lab-planning-check - validate GDL roadmap/config planning baseline"
	@echo "  make graphic-design-lab-contracts-check - validate GDL Design Spec/profile contract foundation"

env:
	python3 -m venv .venv_prepress_hub
	.venv_prepress_hub/bin/python -m pip install --upgrade pip
	.venv_prepress_hub/bin/python -m pip install -e '.[dev]'

test:
	$(PYTHON) -m pytest -q

bootstrap-check:
	$(PYTHON) scripts/validation/check_bootstrap_foundation.py

graphic-design-lab-planning-check:
	$(PYTHON) scripts/validation/check_graphic_design_lab_planning.py

graphic-design-lab-contracts-check:
	$(PYTHON) scripts/validation/check_graphic_design_lab_contracts.py

governance-check: bootstrap-check graphic-design-lab-planning-check graphic-design-lab-contracts-check test
	@git diff --check
	@echo "PREPRESS_HUB_GOVERNANCE_CHECK=PASS"

status:
	@git status --short
	@echo "---"
	@cat coordination/status/current_status.yaml
# --- Assistant continuity / fresh-worker commissioning ---

MODULE_ROOT ?= $(CURDIR)
MODULE_ID ?= forprint_prepress_hub
BLUEPRINT_ROOT ?= ../forprint_system_blueprint
MODULE_REGISTRATION_STATE ?= registered
MODULE_ASSISTANT_CONTEXT_CLI ?= scripts/coordination/module_assistant_context.py
SCOPE ?= bootstrap
TOPICS ?=

.PHONY: assistant-handoff-check assistant-pack assistant-context-pack

# Read-only recovery gate for a fresh assistant.
assistant-handoff-check:
	$(PYTHON) $(MODULE_ASSISTANT_CONTEXT_CLI) --module-root "$(MODULE_ROOT)" --module "$(MODULE_ID)" --blueprint-root "$(BLUEPRINT_ROOT)" --registration-state "$(MODULE_REGISTRATION_STATE)" check

# Build MODULE_ONBOARD under ignored tmp/ only.
assistant-pack: assistant-handoff-check
	$(PYTHON) $(MODULE_ASSISTANT_CONTEXT_CLI) --module-root "$(MODULE_ROOT)" --module "$(MODULE_ID)" --blueprint-root "$(BLUEPRINT_ROOT)" --registration-state "$(MODULE_REGISTRATION_STATE)" pack --package-type MODULE_ONBOARD --scope bootstrap

# Build bounded MODULE_CONTEXT under ignored tmp/ only.
assistant-context-pack: assistant-handoff-check
	$(PYTHON) $(MODULE_ASSISTANT_CONTEXT_CLI) --module-root "$(MODULE_ROOT)" --module "$(MODULE_ID)" --blueprint-root "$(BLUEPRINT_ROOT)" --registration-state "$(MODULE_REGISTRATION_STATE)" pack --package-type MODULE_CONTEXT --scope "$(SCOPE)" --topics "$(TOPICS)"

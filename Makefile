.PHONY: help env test bootstrap-check governance-check status graphic-design-lab-planning-check graphic-design-lab-contracts-check graphic-design-lab-svg-check gdl-intake-handoff-check

PYTHON ?= .venv_prepress_hub/bin/python

help:
	@echo "ForPrint Prepress Hub operator map"
	@echo "  make env              - create/update dedicated Python environment"
	@echo "  make test             - run repository tests"
	@echo "  make bootstrap-check  - validate bootstrap foundation"
	@echo "  make governance-check - run current local governance checks"
	@echo "  make status           - show Git and module status"
	@echo "  make graphic-design-lab-planning-check - validate GDL roadmap/catalog/evidence/config planning baseline"
	@echo "  make graphic-design-lab-contracts-check - validate GDL Design Spec/profile contract foundation"
	@echo "  make graphic-design-lab-svg-check - compile and structurally validate deterministic editable SVG"
	@echo "  make gdl-intake-handoff-check - validate Product Playbook, Guided Intake and Creator Handoff"
	@echo "  make blueprint-prompts-check - verify Prepress Blueprint prompt queue is readable"
	@echo "  make blueprint-prompts-sync  - synchronize Blueprint prompt into local received/active/terminal state"
	@echo "  make blueprint-prompt-check  - validate local prompt lifecycle state"
	@echo "  make blueprint-prompt-status - show active/terminal local prompt metadata"
	@echo "  make prompt-read-next         - print the active local prompt"

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

graphic-design-lab-svg-check:
	$(PYTHON) scripts/validation/check_graphic_design_lab_svg_compiler.py

gdl-intake-handoff-check:
	$(PYTHON) scripts/validation/check_graphic_design_lab_intake_handoff.py

governance-check: bootstrap-check graphic-design-lab-planning-check graphic-design-lab-contracts-check graphic-design-lab-svg-check gdl-intake-handoff-check test
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

# --- Blueprint prompt intake / module-owned synchronization ---

BLUEPRINT_PROMPT_INDEX ?= $(BLUEPRINT_ROOT)/coordination/outgoing_prompts/$(MODULE_ID)/index.yaml
BLUEPRINT_PROMPT_MODULE_DIR ?= $(BLUEPRINT_ROOT)/coordination/outgoing_prompts/$(MODULE_ID)
LOCAL_PROMPT_DIR ?= coordination/prompts/received
LOCAL_ACTIVE_PROMPT_DIR ?= coordination/prompts/active
LOCAL_ARCHIVED_PROMPT_DIR ?= coordination/prompts/archived
LOCAL_PROMPT_INDEX ?= coordination/prompts/index.yaml
PROMPT_STATE_SYNC ?= scripts/coordination/sync_prompt_state.py
PROMPT_ID ?=

.PHONY: blueprint-prompts-list blueprint-prompts-check blueprint-prompts-sync \
        blueprint-prompt blueprint-prompt-check blueprint-prompt-status prompt-read-next

# Read-only view of Blueprint-owned approved prompt artifacts.
blueprint-prompts-list:
	@test -d "$(BLUEPRINT_PROMPT_MODULE_DIR)/approved"
	@find "$(BLUEPRINT_PROMPT_MODULE_DIR)/approved" -maxdepth 1 -type f -name '*.md' | sort

# Read-only queue availability check. Never mutates Blueprint.
blueprint-prompts-check:
	@test -f "$(BLUEPRINT_PROMPT_INDEX)"
	@test -d "$(BLUEPRINT_PROMPT_MODULE_DIR)/approved"
	@echo "PREPRESS_BLUEPRINT_PROMPT_QUEUE_READABLE=PASS"
	@echo "SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS=READ_ONLY_STRICT"

# Module-owned synchronization. Source queue is read-only; all writes remain local.
blueprint-prompts-sync: blueprint-prompts-check
	$(PYTHON) $(PROMPT_STATE_SYNC) \
		--module-id "$(MODULE_ID)" \
		--blueprint-index "$(BLUEPRINT_PROMPT_INDEX)" \
		--blueprint-module-dir "$(BLUEPRINT_PROMPT_MODULE_DIR)" \
		--received-dir "$(LOCAL_PROMPT_DIR)" \
		--active-dir "$(LOCAL_ACTIVE_PROMPT_DIR)" \
		--archived-dir "$(LOCAL_ARCHIVED_PROMPT_DIR)" \
		--local-index "$(LOCAL_PROMPT_INDEX)" \
		--status-yaml coordination/status/current_status.yaml \
		--status-md coordination/status/current_status.md \
		--prompt-id "$(PROMPT_ID)"

# Print exactly one active local prompt.
blueprint-prompt:
	@count="$$(find "$(LOCAL_ACTIVE_PROMPT_DIR)" -maxdepth 1 -type f -name '*.md' | wc -l)"; \
		test "$$count" -eq 1 || \
		(echo "Expected exactly one active local prompt, found $$count."; exit 1)
	@cat "$$(find "$(LOCAL_ACTIVE_PROMPT_DIR)" -maxdepth 1 -type f -name '*.md' | sort | head -n 1)"

prompt-read-next: blueprint-prompt

blueprint-prompt-check:
	$(PYTHON) $(PROMPT_STATE_SYNC) \
		--local-index "$(LOCAL_PROMPT_INDEX)" \
		--status-yaml coordination/status/current_status.yaml \
		--received-dir "$(LOCAL_PROMPT_DIR)" \
		--active-dir "$(LOCAL_ACTIVE_PROMPT_DIR)" \
		--check-only

blueprint-prompt-status:
	$(PYTHON) $(PROMPT_STATE_SYNC) \
		--local-index "$(LOCAL_PROMPT_INDEX)" \
		--status-only

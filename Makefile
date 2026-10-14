.PHONY: help env test bootstrap-check governance-check status graphic-design-lab-planning-check graphic-design-lab-contracts-check graphic-design-lab-svg-check gdl-intake-handoff-check gdl-empirical-check gdl-empirical-index gdl-empirical-summary gdl-result-package-check gdl-toolchain-contract-check gdl-toolchain-check gdl-greeting-card-freeze-check gdl-project-first-check gdl-greeting-card-prototype gdl-greeting-card-corpus-validate

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
	@echo "  make gdl-result-package-check - validate deterministic GDL Creator Result Package foundation"
	@echo "  make gdl-toolchain-contract-check - validate portable GDL PDF/toolchain contract"
	@echo "  make gdl-toolchain-check - validate installed GDL PDF/vector/raster host toolchain"
	@echo "  make gdl-greeting-card-freeze-check - validate canonical recurring greeting-card structural freeze"
	@echo "  make gdl-greeting-card-builder-input-check - validate exact Builder v1 input extension over the Accepted Constructor Bundle"
	@echo "  make gdl-greeting-card-private-resources-check RESOURCE_MANIFEST=/private/path/resources.yaml - fail-closed validation of exact Builder v1 private resources"
	@echo "  make gdl-greeting-card-embedded-components-check RESOURCE_MANIFEST=/private/path/resources.yaml - validate sender-logo and all v1 signature template components"
	@echo "  make gdl-greeting-card-builder BUNDLE=/path/to/builder-ready-bundle RESOURCE_MANIFEST=/private/path/resources.yaml ARTIFACT_MANIFEST=/private/path/artifacts.yaml OUTPUT=/private/output - render supported deterministic PDF Builder slice"
	@echo "  make gdl-greeting-card-prototype - run project-owned recurring greeting-card prototype generator"
	@echo "  make gdl-greeting-card-corpus-validate - classify and validate all recurring greeting-card front families"
	@echo "  make gdl-greeting-card-constructor-ingest BUNDLE=/path/to/accepted_constructor_bundle - validate and ingest one accepted constructor bundle"
	@echo "  make gdl-greeting-card-smb-launch SHARE=In_Progress RELATIVE_PATH_B64=<token> - resolve SMB bundle path and invoke canonical constructor ingest"
	@echo "  make gdl-greeting-card-intake-handoff-config - one-time binding to private resource library"
	@echo "  make gdl-greeting-card-intake-handoff-preflight PACKAGE=/share/client/gdl_intake_handoff.zip - check finalized Intake package"
	@echo "  make gdl-greeting-card-intake-handoff-run PACKAGE=/share/client/gdl_intake_handoff.zip - ingest and generate full review PDFs"
	@echo "  make gdl-greeting-card-cycle-closeout-check MANIFEST=tmp/private_cycle.yaml - verify review artifacts (no production approval)"
	@echo "  make gdl-greeting-card-cycle-closeout-record MANIFEST=tmp/private_cycle.yaml - record private review receipt"
	@echo "  make gdl-project-first-check - validate project-internal-tooling-first execution rule"
	@echo "  make gdl-accept-and-advance REQUEST=tmp/<request>.yaml [APPLY=1 CONFIRM=<operation-id>] - preview/apply explicit governed GDL lifecycle transition"
	@echo "  make gdl-accept-and-advance-check - validate local governed transition tooling"
	@echo "  make gdl-transition-closeout-review - review exact latest GDL transition write-set"
	@echo "  make gdl-transition-closeout-apply CONFIRM=YES - exact-stage, commit, push and verify latest GDL transition"
	@echo "  make gdl-closeout-review - review exact GDL closeout write-set"
	@echo "  make gdl-closeout-apply CONFIRM=YES - exact-stage, commit, push and verify reviewed slice"
	@echo "  make gdl-empirical-check - validate GDL empirical case semantics and privacy boundaries"
	@echo "  make gdl-empirical-index - print deterministic GDL empirical evidence discovery index"
	@echo "  make gdl-empirical-summary - print human-readable GDL empirical evidence summary"
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

gdl-result-package-check:
	$(PYTHON) scripts/validation/check_graphic_design_lab_creator_result_package.py

gdl-toolchain-contract-check:
	$(PYTHON) scripts/validation/check_gdl_toolchain_readiness.py --mode contract

gdl-toolchain-check: gdl-toolchain-contract-check
	$(PYTHON) scripts/validation/check_gdl_toolchain_readiness.py --mode host

gdl-greeting-card-freeze-check:
	$(PYTHON) scripts/validation/check_graphic_design_lab_greeting_card_freeze.py

gdl-project-first-check:
	$(PYTHON) scripts/validation/check_graphic_design_lab_project_first.py

GDL_GREETING_CARD_PROTOTYPE_TOOL ?= scripts/graphic_design_lab/greeting_cards/prototype.py
GDL_GREETING_CARD_CLIENT_ROOT ?= $(GDL_CLIENT_ROOT)
GDL_GREETING_CARD_SAMPLE_DIR ?= 20.09.26
GDL_GREETING_CARD_REFERENCE ?= dolinska.pdf
GDL_GREETING_CARD_OUTPUT ?= tmp/gdl_prototypes/greeting_card_current
GDL_GREETING_CARD_CORPUS_OUTPUT ?= tmp/gdl_prototypes/greeting_card_corpus_validation

gdl-greeting-card-prototype:
	@test -n "$(GDL_GREETING_CARD_CLIENT_ROOT)" || (echo "Set GDL_CLIENT_ROOT or GDL_GREETING_CARD_CLIENT_ROOT."; exit 2)
	$(PYTHON) $(GDL_GREETING_CARD_PROTOTYPE_TOOL) --client-root "$(GDL_GREETING_CARD_CLIENT_ROOT)" --sample-dir "$(GDL_GREETING_CARD_SAMPLE_DIR)" --reference "$(GDL_GREETING_CARD_REFERENCE)" --output "$(GDL_GREETING_CARD_OUTPUT)"

gdl-greeting-card-corpus-validate:
	@test -n "$(GDL_GREETING_CARD_CLIENT_ROOT)" || (echo "Set GDL_CLIENT_ROOT or GDL_GREETING_CARD_CLIENT_ROOT."; exit 2)
	$(PYTHON) $(GDL_GREETING_CARD_PROTOTYPE_TOOL) --mode corpus-validate --client-root "$(GDL_GREETING_CARD_CLIENT_ROOT)" --sample-dir "$(GDL_GREETING_CARD_SAMPLE_DIR)" --output "$(GDL_GREETING_CARD_CORPUS_OUTPUT)"

governance-check: bootstrap-check graphic-design-lab-planning-check graphic-design-lab-contracts-check graphic-design-lab-svg-check gdl-intake-handoff-check gdl-result-package-check gdl-toolchain-contract-check gdl-greeting-card-freeze-check gdl-project-first-check gdl-empirical-check test
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

GDL_EMPIRICAL_TOOL ?= scripts/coordination/gdl_empirical_learning.py
GDL_EMPIRICAL_FIXTURE ?= tests/fixtures/graphic_design_lab/gdl_empirical_case_menu_sanitized_v0_1.yaml

gdl-empirical-check:
	$(PYTHON) $(GDL_EMPIRICAL_TOOL) validate --case "$(GDL_EMPIRICAL_FIXTURE)"

gdl-empirical-index:
	$(PYTHON) $(GDL_EMPIRICAL_TOOL) index

gdl-empirical-summary:
	$(PYTHON) $(GDL_EMPIRICAL_TOOL) summary

.PHONY: gdl-greeting-card-illustrator-companion-check
gdl-greeting-card-illustrator-companion-check:
	.venv_prepress_hub/bin/python -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_greeting_card_illustrator_operator_companion_v0_1.py
# --- Project-owned explicit closeout ---

GDL_CLOSEOUT_TOOL ?= scripts/coordination/project_closeout.py
GDL_CLOSEOUT_MANIFEST ?= coordination/graphic_design_lab/execution/greeting_card_operator_companion_closeout_v0_1.json

.PHONY: gdl-closeout-review gdl-closeout-apply

gdl-closeout-review:
	$(PYTHON) $(GDL_CLOSEOUT_TOOL) review --manifest "$(GDL_CLOSEOUT_MANIFEST)"

gdl-closeout-apply:
	@test "$(CONFIRM)" = "YES" || (echo "Explicit confirmation required: CONFIRM=YES"; exit 2)
	$(PYTHON) $(GDL_CLOSEOUT_TOOL) apply --manifest "$(GDL_CLOSEOUT_MANIFEST)" --confirm "$(CONFIRM)"
# --- Project-owned GDL accept-and-advance lifecycle transition ---

GDL_ACCEPT_AND_ADVANCE_TOOL ?= scripts/coordination/gdl_accept_and_advance_v0_1.py
GDL_ACCEPT_AND_ADVANCE_REQUEST ?= $(REQUEST)
GDL_ACCEPT_AND_ADVANCE_APPLY ?= $(APPLY)
GDL_ACCEPT_AND_ADVANCE_CONFIRMATION ?= $(CONFIRM)
GDL_TRANSITION_CLOSEOUT_MANIFEST ?= coordination/graphic_design_lab/execution/current_transition_closeout_v0_1.json

.PHONY: gdl-accept-and-advance gdl-accept-and-advance-check gdl-transition-closeout-review gdl-transition-closeout-apply

gdl-accept-and-advance:
	@test -n "$(GDL_ACCEPT_AND_ADVANCE_REQUEST)" || (echo "Set REQUEST=tmp/<request>.yaml"; exit 2)
	@test "$(GDL_ACCEPT_AND_ADVANCE_APPLY)" = "" -o "$(GDL_ACCEPT_AND_ADVANCE_APPLY)" = "0" -o "$(GDL_ACCEPT_AND_ADVANCE_APPLY)" = "1" || (echo "APPLY must be 0 or 1"; exit 2)
	@if [ "$(GDL_ACCEPT_AND_ADVANCE_APPLY)" = "1" ]; then \
		test -n "$(GDL_ACCEPT_AND_ADVANCE_CONFIRMATION)" || { echo "CONFIRM=<operation-id> required when APPLY=1"; exit 2; }; \
		$(PYTHON) $(GDL_ACCEPT_AND_ADVANCE_TOOL) --root . --request "$(GDL_ACCEPT_AND_ADVANCE_REQUEST)" --apply --operator-confirmation "$(GDL_ACCEPT_AND_ADVANCE_CONFIRMATION)"; \
	else \
		$(PYTHON) $(GDL_ACCEPT_AND_ADVANCE_TOOL) --root . --request "$(GDL_ACCEPT_AND_ADVANCE_REQUEST)"; \
	fi

gdl-accept-and-advance-check:
	$(PYTHON) -m pytest -q -p no:cacheprovider \
		tests/coordination/test_gdl_accept_and_advance_v0_1.py \
		tests/graphic_design_lab/test_gdl_blueprint_pattern_inheritance_v0_1.py

gdl-transition-closeout-review:
	@test -f "$(GDL_TRANSITION_CLOSEOUT_MANIFEST)" || (echo "No current transition closeout manifest"; exit 2)
	$(PYTHON) $(GDL_CLOSEOUT_TOOL) review --manifest "$(GDL_TRANSITION_CLOSEOUT_MANIFEST)"

gdl-transition-closeout-apply:
	@test "$(CONFIRM)" = "YES" || (echo "Explicit confirmation required: CONFIRM=YES"; exit 2)
	@test -f "$(GDL_TRANSITION_CLOSEOUT_MANIFEST)" || (echo "No current transition closeout manifest"; exit 2)
	$(PYTHON) $(GDL_CLOSEOUT_TOOL) apply --manifest "$(GDL_TRANSITION_CLOSEOUT_MANIFEST)" --confirm "$(CONFIRM)"

# --- Greeting-card Builder v1 exact-input extension ---

.PHONY: gdl-greeting-card-builder-input-check

gdl-greeting-card-builder-input-check:
	.venv_prepress_hub/bin/python -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_greeting_card_builder_input_v0_1.py

# --- Greeting-card Builder v1 private-resource resolver ---

GDL_GREETING_CARD_PRIVATE_RESOURCE_CHECKER ?= scripts/graphic_design_lab/greeting_cards/private_resource_check.py
GDL_GREETING_CARD_PRIVATE_RESOURCE_MANIFEST ?= $(RESOURCE_MANIFEST)

.PHONY: gdl-greeting-card-private-resources-check

gdl-greeting-card-private-resources-check:
	@test -n "$(GDL_GREETING_CARD_PRIVATE_RESOURCE_MANIFEST)" || (echo "Set RESOURCE_MANIFEST=/private/path/resources.yaml"; exit 2)
	$(PYTHON) $(GDL_GREETING_CARD_PRIVATE_RESOURCE_CHECKER) --manifest "$(GDL_GREETING_CARD_PRIVATE_RESOURCE_MANIFEST)"

# --- Greeting-card embedded template components ---

GDL_GREETING_CARD_EMBEDDED_COMPONENT_CHECKER ?= scripts/graphic_design_lab/greeting_cards/embedded_component_check.py
GDL_GREETING_CARD_EMBEDDED_COMPONENT_RESOURCE_MANIFEST ?= $(RESOURCE_MANIFEST)

.PHONY: gdl-greeting-card-embedded-components-check

gdl-greeting-card-embedded-components-check:
	@test -n "$(GDL_GREETING_CARD_EMBEDDED_COMPONENT_RESOURCE_MANIFEST)" || (echo "Set RESOURCE_MANIFEST=/private/path/resources.yaml"; exit 2)
	$(PYTHON) $(GDL_GREETING_CARD_EMBEDDED_COMPONENT_CHECKER) --manifest "$(GDL_GREETING_CARD_EMBEDDED_COMPONENT_RESOURCE_MANIFEST)" --signature-variant ALL

# --- Greeting-card accepted-constructor-bundle ingest ---

GDL_GREETING_CARD_CONSTRUCTOR_RUNNER ?= scripts/graphic_design_lab/greeting_cards/job_runner.py
GDL_GREETING_CARD_BUNDLE ?= $(BUNDLE)

.PHONY: gdl-greeting-card-constructor-ingest

gdl-greeting-card-constructor-ingest:
	@test -n "$(GDL_GREETING_CARD_BUNDLE)" || (echo "Set BUNDLE=/path/to/accepted_constructor_bundle"; exit 2)
	$(PYTHON) $(GDL_GREETING_CARD_CONSTRUCTOR_RUNNER) --bundle "$(GDL_GREETING_CARD_BUNDLE)"

# --- Greeting-card SMB/local one-click launcher bridge ---

GDL_GREETING_CARD_SMB_LAUNCH_BRIDGE ?= scripts/graphic_design_lab/greeting_cards/smb_launcher_bridge.py
GDL_GREETING_CARD_SMB_SHARE ?= $(SHARE)
GDL_GREETING_CARD_SMB_RELATIVE_PATH_B64 ?= $(RELATIVE_PATH_B64)

.PHONY: gdl-greeting-card-smb-launch

gdl-greeting-card-smb-launch:
	@test -n "$(GDL_GREETING_CARD_SMB_SHARE)" || (echo "Set SHARE=In_Progress"; exit 2)
	@test -n "$(GDL_GREETING_CARD_SMB_RELATIVE_PATH_B64)" || (echo "Set RELATIVE_PATH_B64=<base64url-token>"; exit 2)
	$(PYTHON) $(GDL_GREETING_CARD_SMB_LAUNCH_BRIDGE) --share "$(GDL_GREETING_CARD_SMB_SHARE)" --relative-path-b64 "$(GDL_GREETING_CARD_SMB_RELATIVE_PATH_B64)"

# --- Greeting-card deterministic PDF Builder v0.1 ---

GDL_GREETING_CARD_BUILDER ?= scripts/graphic_design_lab/greeting_cards/builder.py
GDL_GREETING_CARD_BUILDER_BUNDLE ?= $(BUNDLE)
GDL_GREETING_CARD_BUILDER_RESOURCE_MANIFEST ?= $(RESOURCE_MANIFEST)
GDL_GREETING_CARD_BUILDER_ARTIFACT_MANIFEST ?= $(ARTIFACT_MANIFEST)
GDL_GREETING_CARD_BUILDER_OUTPUT ?= $(OUTPUT)

.PHONY: gdl-greeting-card-builder

gdl-greeting-card-builder:
	@test -n "$(GDL_GREETING_CARD_BUILDER_BUNDLE)" || (echo "Set BUNDLE=/path/to/builder-ready-bundle"; exit 2)
	@test -n "$(GDL_GREETING_CARD_BUILDER_RESOURCE_MANIFEST)" || (echo "Set RESOURCE_MANIFEST=/private/path/resources.yaml"; exit 2)
	@test -n "$(GDL_GREETING_CARD_BUILDER_ARTIFACT_MANIFEST)" || (echo "Set ARTIFACT_MANIFEST=/private/path/artifacts.yaml"; exit 2)
	@test -n "$(GDL_GREETING_CARD_BUILDER_OUTPUT)" || (echo "Set OUTPUT=/private/output"; exit 2)
	$(PYTHON) $(GDL_GREETING_CARD_BUILDER) --bundle "$(GDL_GREETING_CARD_BUILDER_BUNDLE)" --resource-manifest "$(GDL_GREETING_CARD_BUILDER_RESOURCE_MANIFEST)" --artifact-manifest "$(GDL_GREETING_CARD_BUILDER_ARTIFACT_MANIFEST)" --output-dir "$(GDL_GREETING_CARD_BUILDER_OUTPUT)"

# BEGIN GC09 FULL FOUR PAGE REVIEW V0.1
# Review-only: never accepts a customer order or enables production.
GDL_GC09_REVIEW_INPUTS ?= tmp/gdl_gc09b_real_pdf_proof_20261010/private_inputs_local.json
GDL_GC09_REVIEW_OUTPUT ?= tmp/gdl_gc09_full_card_review
GDL_GC09_REVIEW_CLI ?= scripts/graphic_design_lab/greeting_cards/full_review_runner_v0_1.py
.PHONY: gdl-greeting-card-final-review-preflight gdl-greeting-card-final-review
gdl-greeting-card-final-review-preflight:
	$(PYTHON) $(GDL_GC09_REVIEW_CLI) --mode preflight --inputs-config "$(GDL_GC09_REVIEW_INPUTS)" --output-root "$(GDL_GC09_REVIEW_OUTPUT)"
gdl-greeting-card-final-review:
	$(PYTHON) $(GDL_GC09_REVIEW_CLI) --mode run --inputs-config "$(GDL_GC09_REVIEW_INPUTS)" --output-root "$(GDL_GC09_REVIEW_OUTPUT)"
# END GC09 FULL FOUR PAGE REVIEW V0.1

# BEGIN GC-E2E INTAKE -> EXISTING BUILDER HANDOFF V0.1
# Review-only; resource library is configured once in ignored tmp/.
GDL_INTAKE_HANDOFF_CLI ?= scripts/graphic_design_lab/greeting_cards/intake_handoff_runner_v0_1.py
GDL_INTAKE_HANDOFF_PACKAGE ?= $(PACKAGE)
GDL_INTAKE_PRIVATE_INPUTS ?= tmp/gdl_gc09b_real_pdf_proof_20261010/private_inputs_local.json
.PHONY: gdl-greeting-card-intake-handoff-config gdl-greeting-card-intake-handoff-preflight gdl-greeting-card-intake-handoff-run

gdl-greeting-card-intake-handoff-config:
	$(PYTHON) $(GDL_INTAKE_HANDOFF_CLI) --mode init-config --from-inputs-config "$(GDL_INTAKE_PRIVATE_INPUTS)"

gdl-greeting-card-intake-handoff-preflight:
	@test -n "$(GDL_INTAKE_HANDOFF_PACKAGE)" || (echo "Set PACKAGE=/path/to/gdl_intake_handoff.zip"; exit 2)
	$(PYTHON) $(GDL_INTAKE_HANDOFF_CLI) --mode preflight --package "$(GDL_INTAKE_HANDOFF_PACKAGE)"

gdl-greeting-card-intake-handoff-run:
	@test -n "$(GDL_INTAKE_HANDOFF_PACKAGE)" || (echo "Set PACKAGE=/path/to/gdl_intake_handoff.zip"; exit 2)
	$(PYTHON) $(GDL_INTAKE_HANDOFF_CLI) --mode run --package "$(GDL_INTAKE_HANDOFF_PACKAGE)"
# END GC-E2E INTAKE -> EXISTING BUILDER HANDOFF V0.1

# BEGIN GDL GENERIC REVIEW CYCLE CLOSEOUT V0.1
# Generic and review-only: never dispatches Creator, accepts orders or prints.
GDL_GC_CYCLE_CLOSEOUT_CLI ?= scripts/graphic_design_lab/greeting_cards/cycle_closeout_v0_1.py
GDL_GC_CYCLE_MANIFEST ?= $(MANIFEST)
.PHONY: gdl-greeting-card-cycle-closeout-check gdl-greeting-card-cycle-closeout-record
gdl-greeting-card-cycle-closeout-check:
	@test -n "$(GDL_GC_CYCLE_MANIFEST)" || (echo "Set MANIFEST=tmp/private_cycle.yaml"; exit 2)
	$(PYTHON) $(GDL_GC_CYCLE_CLOSEOUT_CLI) --mode check --manifest "$(GDL_GC_CYCLE_MANIFEST)"
gdl-greeting-card-cycle-closeout-record:
	@test -n "$(GDL_GC_CYCLE_MANIFEST)" || (echo "Set MANIFEST=tmp/private_cycle.yaml"; exit 2)
	$(PYTHON) $(GDL_GC_CYCLE_CLOSEOUT_CLI) --mode record --manifest "$(GDL_GC_CYCLE_MANIFEST)"
# END GDL GENERIC REVIEW CYCLE CLOSEOUT V0.1

# GC-E2E-09C: dual source-verified signature-component proof only.
# Not a full greeting card and does NOT enable DUAL Builder/runtime execution.
GDL_GC09_DUAL_COMPONENT_CANDIDATE_CLI ?= scripts/graphic_design_lab/greeting_cards/dual_component_candidate_v0_1.py
.PHONY: gdl-greeting-card-dual-component-candidate
gdl-greeting-card-dual-component-candidate:
	@test -n "$(RESOURCE_MANIFEST)" || (echo "Set RESOURCE_MANIFEST=/private/resources.yaml"; exit 2)
	@test -n "$(OUTPUT)" || (echo "Set OUTPUT=tmp/private_dual_component_proof"; exit 2)
	$(PYTHON) $(GDL_GC09_DUAL_COMPONENT_CANDIDATE_CLI) --manifest "$(RESOURCE_MANIFEST)" --output-root "$(OUTPUT)"


# GC-E2E-09C: source-locked DUAL Page4 review candidate, NOT Builder runtime.
GDL_GC09_DUAL_PAGE4_CANDIDATE_CLI ?= scripts/graphic_design_lab/greeting_cards/dual_page4_candidate_v0_1.py
.PHONY: gdl-greeting-card-dual-page4-candidate
gdl-greeting-card-dual-page4-candidate:
	@test -n "$(RESOURCE_MANIFEST)" || (echo "Set RESOURCE_MANIFEST=tmp/private_resources.yaml"; exit 2)
	@test -n "$(PRIOR_COMPONENT_REPORT)" || (echo "Set PRIOR_COMPONENT_REPORT=tmp/private_component_report.json"; exit 2)
	@test -n "$(OUTPUT)" || (echo "Set OUTPUT=tmp/private_page4_proof"; exit 2)
	$(PYTHON) $(GDL_GC09_DUAL_PAGE4_CANDIDATE_CLI) --manifest "$(RESOURCE_MANIFEST)" --prior-component-report "$(PRIOR_COMPONENT_REPORT)" --output-root "$(OUTPUT)"

# GC09D private DUAL full-card candidate; no standard runtime or publish.
GDL_GC09_DUAL_FULL_CARD_CANDIDATE_CLI ?= scripts/graphic_design_lab/greeting_cards/dual_full_card_candidate_v0_1.py
GDL_GC09_DUAL_CANDIDATE_MODE ?= preflight
.PHONY: gdl-greeting-card-dual-full-card-candidate
gdl-greeting-card-dual-full-card-candidate:
	@test -n "$(INPUTS_CONFIG)" || (echo "INPUTS_CONFIG is required"; exit 2)
	@test -n "$(PRIOR_PAGE4_REPORT)" || (echo "PRIOR_PAGE4_REPORT is required"; exit 2)
	@test -n "$(OUTPUT)" || (echo "OUTPUT is required"; exit 2)
	$(PYTHON) $(GDL_GC09_DUAL_FULL_CARD_CANDIDATE_CLI) --mode "$(GDL_GC09_DUAL_CANDIDATE_MODE)" --inputs-config "$(INPUTS_CONFIG)" --prior-page4-report "$(PRIOR_PAGE4_REPORT)" --output-root "$(OUTPUT)"

# BEGIN GC-E2E-10 UNIFIED PRIVATE CYCLE V0.1
# Private review-only, formally verifies constructor chain, no customer publication.
GDL_GC10_UNIFIED_PRIVATE_CLI ?= scripts/graphic_design_lab/greeting_cards/unified_private_cycle_v0_1.py
GDL_GC10_PACKAGE ?= $(PACKAGE)
GDL_GC10_CONFIG ?= tmp/gdl_intake_handoff_runtime_v0_1/local_config.json
GDL_GC10_ALLOW_REPEAT ?= false
.PHONY: gdl-greeting-card-unified-private-preflight gdl-greeting-card-unified-private-cycle
gdl-greeting-card-unified-private-preflight:
	@test -n "$(GDL_GC10_PACKAGE)" || (echo "Set PACKAGE=/path/to/gdl_intake_handoff.zip"; exit 2)
	$(PYTHON) $(GDL_GC10_UNIFIED_PRIVATE_CLI) --mode preflight --package "$(GDL_GC10_PACKAGE)" --config "$(GDL_GC10_CONFIG)"
gdl-greeting-card-unified-private-cycle:
	@test -n "$(GDL_GC10_PACKAGE)" || (echo "Set PACKAGE=/path/to/gdl_intake_handoff.zip"; exit 2)
	@test "$(GDL_GC10_ALLOW_REPEAT)" = "false" -o "$(GDL_GC10_ALLOW_REPEAT)" = "true" || (echo "Set GDL_GC10_ALLOW_REPEAT=false|true"; exit 2)
	$(PYTHON) $(GDL_GC10_UNIFIED_PRIVATE_CLI) --mode run --package "$(GDL_GC10_PACKAGE)" --config "$(GDL_GC10_CONFIG)" $(if $(filter true,$(GDL_GC10_ALLOW_REPEAT)),--allow-repeat,)
# END GC-E2E-10 UNIFIED PRIVATE CYCLE V0.1

# BEGIN GC14 CLIENT SMB WORKSPACE INPUT QUEUE V0.1
# Only final accepted handoffs enter GC10; Intake staging yields BLOCKED report.
GDL_GC14_QUEUE_CLI ?= scripts/graphic_design_lab/greeting_cards/smb_workspace_queue_v0_1.py
GDL_GC14_SHARE ?= $(SHARE)
GDL_GC14_WORKSPACE_RELATIVE_B64 ?= $(WORKSPACE_RELATIVE_B64)
.PHONY: gdl-greeting-card-smb-queue

gdl-greeting-card-smb-queue:
	@test -n "$(GDL_GC14_SHARE)" || (echo "Set SHARE=In_Progress"; exit 2)
	@test -n "$(GDL_GC14_WORKSPACE_RELATIVE_B64)" || (echo "Set WORKSPACE_RELATIVE_B64=..."; exit 2)
	$(PYTHON) $(GDL_GC14_QUEUE_CLI) --mode run --share "$(GDL_GC14_SHARE)" --workspace-relative-b64 "$(GDL_GC14_WORKSPACE_RELATIVE_B64)"
# END GC14 CLIENT SMB WORKSPACE INPUT QUEUE V0.1

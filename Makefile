PYTHON ?= python3
HARNESSES := codex opencode cursor gemini copilot

.PHONY: generate generate-codex generate-opencode generate-cursor generate-gemini generate-copilot generate-all docs check-drift garden release-check validate test clean clean-generated install-opencode uninstall-opencode install-copilot uninstall-copilot

generate:
ifdef HARNESS
	$(PYTHON) tools/generate.py --harness $(HARNESS) $(if $(PLUGIN),--plugin $(PLUGIN),--all)
else
	$(PYTHON) tools/generate.py --harness all
endif

generate-codex:
	$(PYTHON) tools/generate.py --harness codex

generate-opencode:
	$(PYTHON) tools/generate.py --harness opencode

generate-cursor:
	$(PYTHON) tools/generate.py --harness cursor

generate-gemini:
	$(PYTHON) tools/generate.py --harness gemini

generate-copilot:
	$(PYTHON) tools/generate.py --harness copilot

generate-all: generate

docs:
	$(PYTHON) tools/generate.py --docs-only

check-drift:
	$(PYTHON) tools/generate.py --harness all --check

garden:
	$(PYTHON) tools/doc_gardener.py $(if $(STRICT),--strict)

release-check: check-drift
	$(PYTHON) tools/validate_generated.py --no-generated --strict

validate: generate-all
	$(PYTHON) tools/check_agent_name_collisions.py --fail-on-duplicates
	$(PYTHON) tools/validate_generated.py --strict

test:
	$(PYTHON) -m unittest discover -s tools/tests -v

clean:
	$(PYTHON) tools/generate.py --harness all --clean

clean-generated: clean

install-opencode:
	$(PYTHON) tools/generate.py --harness opencode --all --prune
	$(PYTHON) tools/install_opencode.py install $(if $(filter 1 true TRUE yes YES,$(FORCE)),--force)

uninstall-opencode:
	$(PYTHON) tools/install_opencode.py uninstall

install-copilot:
	$(PYTHON) tools/generate.py --harness copilot --all --prune
	$(PYTHON) tools/install_copilot.py install $(if $(filter 1 true TRUE yes YES,$(FORCE)),--force)

uninstall-copilot:
	$(PYTHON) tools/install_copilot.py uninstall

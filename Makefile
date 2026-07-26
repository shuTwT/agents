PYTHON ?= python3

.PHONY: generate generate-codex generate-opencode generate-all docs check-drift release-check validate test clean

generate:
	$(PYTHON) tools/generate.py --harness all

generate-codex:
	$(PYTHON) tools/generate.py --harness codex

generate-opencode:
	$(PYTHON) tools/generate.py --harness opencode

generate-all: generate

docs:
	$(PYTHON) tools/generate.py --docs-only

check-drift:
	$(PYTHON) tools/generate.py --harness all --check

release-check: generate-all
	$(PYTHON) tools/validate.py --strict

validate: generate-all
	$(PYTHON) tools/validate.py --strict

test: generate-all
	$(PYTHON) -m unittest discover -s tests -v

clean:
	$(PYTHON) tools/generate.py --harness all --clean

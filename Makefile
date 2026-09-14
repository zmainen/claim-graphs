# Gates for the machinery. The corpus lives in its own repository; targets that need one say so.
#
# A checkout of a corpus is optional. Without it the suite runs and four prompt-contract tests
# skip, because the contract renders real claim pairs as its worked examples. With it, point
# CLAIM_GRAPHS_CORPUS_DIR at the corpus's claims/ directory and everything runs.
#
#   make check                                    # 110 tests, 4 skipped
#   make check CORPUS=path/to/corpus/claims   # 114 tests

PYTHON ?= python3
CORPUS ?=
ifneq ($(CORPUS),)
export CLAIM_GRAPHS_CORPUS_DIR = $(CORPUS)
endif

.PHONY: help check contract skill validate test

help:  ## Show this help
	@grep -hE '^[a-z][a-zA-Z0-9_-]*:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

check:  ## Gates that are clean on main. A failure here is this change's fault.
	cd extract && $(PYTHON) -c "import claim_graphs.cli, claim_graphs.edges, claim_graphs.layers, claim_graphs.write, claim_graphs.sources"
	cd extract && $(PYTHON) tests/test_layer_contract.py
	cd extract && $(PYTHON) tests/test_sources.py
	cd extract && $(PYTHON) tests/test_pandoc_source.py
	# The flat-text branch of prepare(). No corpus here exercises it — every eLife paper is
	# JATS — which is how it sat broken for the life of the repository (#47).
	cd extract && $(PYTHON) tests/test_flat_text_path.py
	# Replicates are peers, not versions, and two models are not one distribution.
	$(PYTHON) scripts/test_replicates.py
	cd extract && $(PYTHON) tests/test_claimset.py
	# What a claim approval is granted to. Every field wrongly in the hash voids real
	# judgements for a reason unrelated to them.
	cd extract && $(PYTHON) tests/test_claim_approval.py
	$(PYTHON) scripts/standards_report.py --check
	node js/test-claim-set.mjs
	cd extract && $(PYTHON) tests/test_prompt_contract.py
	cd extract && $(PYTHON) tests/test_profiles.py
	cd extract && $(PYTHON) tests/test_skill.py
	cd extract && $(PYTHON) tests/test_config_roots.py
	cd extract && $(PYTHON) tests/test_one_frontmatter_parser.py
	cd extract && $(PYTHON) tests/test_edge_scoring.py
	cd extract && $(PYTHON) tests/test_evaluate_precision_and_edges.py
	cd extract && $(PYTHON) tests/test_verdicts.py
	$(PYTHON) scripts/test_warrant.py
	$(PYTHON) scripts/test_pipeline_versions.py
	# No runner may derive a corpus path from its own location (#50).
	$(PYTHON) scripts/test_roots.py
	$(PYTHON) scripts/test_agent_mode.py

test:  ## The whole suite under pytest
	cd extract && $(PYTHON) -m pytest tests/ -q

contract:  ## Regenerate the prompt contract from vocabulary.py, relations.py and schema.py
	@test -n "$(CLAIM_GRAPHS_CORPUS_DIR)" || { echo "needs a corpus: make contract CORPUS=/path/to/claims"; exit 1; }
	cd extract && $(PYTHON) -m claim_graphs.cli contract --write

skill:  ## Regenerate the agent-facing skill from docs/skill/ and the declarations
	@test -n "$(CLAIM_GRAPHS_CORPUS_DIR)" || { echo "needs a corpus: make skill CORPUS=/path/to/claims"; exit 1; }
	cd extract && $(PYTHON) -m claim_graphs.cli skill --write

standards:  ## Regenerate the standards table from standards.yaml
	$(PYTHON) scripts/standards_report.py --write

validate:  ## SHACL-validate MIRA exports (needs pyshacl, and exports to validate)
	$(PYTHON) scripts/validate_mira.py

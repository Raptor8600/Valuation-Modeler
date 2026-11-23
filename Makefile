.PHONY: test verify check docs site app snapshots
test:        ## full test suite (needs LibreOffice for the parity tests)
	python -m pytest -q tests
verify:      ## regenerate VERIFICATION_REPORT.md and verification/numbers.json
	python -m scripts.verify
check:       ## CI: fail on any test failure or numeric drift
	python -m scripts.verify --check
docs:        ## regenerate docs from formulas.yaml / assumptions.yaml / the engine
	python -m scripts.gen_docs
snapshots:   ## rebuild the committed reference snapshots
	python -m scripts.reconstruct_ddog_snapshot && python -m scripts.make_synthetic_snapshots
app:
	streamlit run app.py
site:        ## build the documentation portal site/index.html
	python -m scripts.build_site

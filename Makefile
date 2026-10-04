PYTHON ?= python3

.PHONY: help seed commitments shares wayback oghist membership build panel controls final validate test clean

help:
	@echo "seed         Re-seed data/manual/accession_dates.csv from data/extracted/commitments.csv"
	@echo "commitments  Build data/extracted/commitments.csv (observed lending)"
	@echo "wayback      Re-fetch EBRD/IsDB historical shareholder data from the Wayback Machine"
	@echo "shares       Build data/extracted/shareholders_panel.csv (does not fetch; run wayback first)"
	@echo "oghist       Fetch and parse World Bank OGHIST + current classification (Component D, IBRD/IDA)"
	@echo "membership   Build data/output/membership.csv (who is a shareholder, and a recipient)"
	@echo "build        Fetch OGHIST, build membership.csv, then combine components A-E into data/output/eligibility.csv"
	@echo "panel        Build data/output/mdb_panel.csv, the estimation panel (eligible dyad-years + lending outcomes)"
	@echo "controls     Build the enriched panel: control variables + project sector/instrument/sovereign breakdown"
	@echo "final        Build data/output/mdb_panel_final.csv: the controls panel + UNGA independent variables"
	@echo "validate     Run every check; exits non-zero while the assertion fails"
	@echo "test         Run the offline unit tests"
	@echo "clean        Remove generated reports (never data/manual)"

seed:
	$(PYTHON) scripts/seed_accession_dates.py

commitments:
	$(PYTHON) scripts/build_afdb_window_breakdown.py
	$(PYTHON) scripts/build_commitments.py

# Hits the Wayback Machine -- may be slow or flaky (see wayback.py's retry
# logic and docs/coding_decisions.md). Re-run is cheap: every successful
# fetch is cached under data/raw/wayback/.
wayback:
	$(PYTHON) scripts/shares_wayback_ebrd.py
	$(PYTHON) scripts/shares_wayback_isdb.py

shares:
	$(PYTHON) scripts/build_shareholders_panel.py

# Fetches from databank(files).worldbank.org and ddh-openapi.worldbank.org --
# cached under data/raw/oghist/, so a re-run is cheap.
oghist:
	$(PYTHON) scripts/build_oghist.py

membership: shares
	$(PYTHON) scripts/build_membership.py

build: oghist membership
	$(PYTHON) scripts/build.py

panel: build commitments
	$(PYTHON) scripts/build_mdb_panel.py

# Reads ../Control variables/datasets/ (a sibling, non-git-tracked folder --
# see docs/coding_decisions.md, 2026-09-27) and needs pandas/pyreadstat
# installed (pip install pandas pyreadstat). wb_region also reads a metadata
# file inside ../Final dataset/Datasets/ (2026-09-28). merge_conflict_crisis_
# lags/build+merge_other_mdb_lending (2026-09-30) are small additive steps
# that overwrite mdb_panel_with_controls.csv in place, adding columns only --
# see docs/coding_decisions.md, 2026-09-30.
controls: panel
	$(PYTHON) scripts/build_control_variables.py
	$(PYTHON) scripts/build_project_breakdown.py
	$(PYTHON) scripts/merge_control_panel.py
	$(PYTHON) scripts/merge_conflict_crisis_lags.py
	$(PYTHON) scripts/build_other_mdb_lending.py
	$(PYTHON) scripts/merge_other_mdb_lending.py
	$(PYTHON) scripts/report_control_coverage.py --by-year data/output/reports/control_coverage_by_year.csv

# Reads ../Final dataset/Datasets/dataverse_files (1)/ (Erik Voeten's UNGA
# ideal-point data, sibling non-git-tracked folder -- see docs/coding_
# decisions.md). Writes data/output/mdb_panel_final.csv and mirrors it,
# plus the codebook deliverables, into ../Final dataset/{output,codebook}/.
# The last step (plot_unga_positions.py) needs matplotlib (pip install
# matplotlib), the only script in this project that uses it.
final: controls
	$(PYTHON) scripts/build_unga_ideal_points.py
	$(PYTHON) scripts/build_shareholder_weights.py
	$(PYTHON) scripts/build_unga_iv.py
	$(PYTHON) scripts/merge_unga_iv.py
	$(PYTHON) scripts/report_largest_shareholders.py
	$(PYTHON) scripts/report_control_coverage.py --panel data/output/mdb_panel_final.csv \
		--report data/output/reports/unga_iv_coverage.csv \
		--by-year data/output/reports/mdb_panel_final_coverage_by_year.csv
	$(PYTHON) scripts/report_control_coverage.py --panel data/output/mdb_panel_final.csv \
		--report "../Final dataset/codebook/variable_coverage.csv"
	$(PYTHON) scripts/plot_unga_positions.py

# Order matters: the reports run before the assertion, so a failing assertion
# still leaves every report on disk to look at. check_revealed is last because
# its non-zero exit is what fails the target.
validate:
	$(PYTHON) scripts/validate_manual.py
	$(PYTHON) scripts/report_panel_balance.py
	$(PYTHON) scripts/report_zero_share.py
	$(PYTHON) scripts/check_revealed.py

test:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	rm -rf data/output/reports

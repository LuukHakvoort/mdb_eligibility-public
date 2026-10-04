"""Build data/extracted/control_variables.csv: a country-year table of
economic, cultural, governance, geographic and "liberal" (democracy/rights)
control variables, from the nine raw sources the user assembled in
``../Control variables/datasets/`` (not a git repo, sibling to this one --
see docs/coding_decisions.md, 2026-09-27, for why it lives there).

**Uses pandas**, unlike the rest of this project's CSV-module pipeline --
justified here because two sources are Stata `.dta` files (V-Dem, PLAD) that
have no pure-Python reader, and the WDI/UN Tourism sources are naturally a
wide numeric pivot pandas is built for. `pip install pandas pyreadstat` (one-
off, mirrors `pdfplumber` being added earlier for PDF parsing).

**One country-code seam, same as everywhere else in this project**:
`_reference.iso3_from_name`/`ISO3_CODES` resolve every name-based source and
filter out non-country aggregate rows (World Bank regional aggregates in
WDI, UN regional/income groupings in UN Tourism). A handful of source-
specific name spellings that don't resolve directly get a small `_FIXUPS`
dict per source (the same pattern every `annual_reports_*.py` parser already
uses) -- anything left unresolved after that is dropped, not guessed, and
reported.

**Per-source real findings** (see docs/coding_decisions.md for the full
account):

- **WDI** (two custom extracts, ~50 indicators): `Country Code` already ISO3,
  but mixed with non-country aggregates ("Africa Eastern and Southern"/AFE)
  -- filtered by `ISO3_CODES` membership, not by name. `".."` is WDI's own
  missing-value marker.
- **RSF Press Freedom Index**: one CSV per year, real gaps at 2001/2003/2011
  /2017 (files never existed), a couple of years have a byte-identical
  "(1)" duplicate (skipped). **Methodology break**: 2002-2021's "Score N" is
  lower-is-better on its own scale; 2022+'s "Score" is a 0-100 higher-is-
  better composite. Kept as two separate, clearly-named columns -- never
  unified, since inverting one to match the other would be a guess about an
  index this project didn't design.
- **Global Restrictions on Religion**: `Nation_fk` is an internal numeric ID,
  not ISO3 -- resolved by `Ctry_EditorialName` instead. Only the two
  headline indices (GRI, SHI) are kept, not the ~80 sub-question columns.
  Real gap: 2002-2006 and 2023-2026 (source only covers 2007-2022).
- **V-Dem**: ~4,000 variables in the full file; only a curated set is kept
  (see `_VDEM_COLUMNS` below) -- electoral/liberal/participatory/deliberative
  /egalitarian democracy indices, corruption, rule of law, civil liberties,
  free expression. Not every V-Dem variable is a control variable this
  thesis needs, and importing all 4,000 would make the merged panel
  unreviewable.
- **PLAD**: leader-*spell* data, not country-year. Reduced by taking the
  leader in office as of 31 December of each year (a still-serving leader's
  `endyear` is null -- treated as ongoing through MAX_YEAR) and exposing
  only `gender`, `ethnicity1` and `geoname` (birthplace) -- the columns this
  database is actually built around (regional/ethnic leader-favoritism
  research), not its full 41-column schema.
- **LGBTI Policy Index**: clean, `ISO`+`Year` directly, no resolution needed.
- **UN Tourism** (3 of ~10 subfolders the user populated): tourism GDP share
  and the SDG tourism-accounting indicator are single-series, clean.
  Employment is kept as one aggregate column
  (`EMPL_TOTL_TOTL_TOTL_TOTL_PRSN`, "tourism employment, total persons"),
  not its full ~50-way sub-sector x gender x employment-status breakdown
  (user's own choice, 2026-09-27). `reporter_area_label` is a country name,
  resolved the same way as everywhere else; UN regional/income-group
  aggregate rows are dropped when they don't resolve.
- **`eu_member`** (2026-09-28): reuses `scripts/components/mandate.py`'s
  `load_eu_membership()`/`_in_closed_list()` directly -- the exact same
  real-dated EU-accession/Brexit spells already used to decide EIB's own
  in-mandate eligibility, so this column can never quietly disagree with
  that existing eligibility logic. Unlike every other source here, this is
  a **closed roster**: every (iso3, year) in `ISO3_CODES x [MIN_YEAR,
  MAX_YEAR]` gets a confident `1`/`0`, never blank -- there is no country
  this project doesn't know the EU status of.
- **`wb_region`** (2026-09-28): the `Region` column from the World Bank
  metadata file bundled with `../Final dataset/Datasets/
  API_SP.POP.TOTL_DS2_en_csv_v2_430592/` (a population download the user
  otherwise doesn't use -- see docs/coding_decisions.md -- but this Region
  taxonomy is standard and identical regardless of which indicator's
  download it ships with, confirmed with the user before reuse). Static
  per country, cross-joined across every year so it merges the same way
  every other source does. Aggregate rows (blank `Region`) are dropped.
- **`ucdp_conflict`/`banking_crisis`** (2026-09-30): both are **closed
  rosters within their source's own documented coverage window** (UCDP/PRIO
  ACD v26.1: 1946-2025; Laeven & Valencia's Systemic Banking Crises
  Database: 1970-2025) -- confident `0`, not blank, for a covered year with
  no listed conflict/crisis; genuinely blank for 2026, which neither source
  covers at all. This is a deliberate exception to "missing years are left
  null": both sources are comprehensive-by-design attempts to catalog every
  conflict/crisis globally within their stated window (the same logic as
  `eu_member`'s closed roster), not partial extracts like WDI or V-Dem.
  UCDP's own codebook caveat -- coverage is "biased against the inclusion
  of conflicts in the earlier decades and in the less-developed world" --
  is inherited by the 0s and is not independently correctable here; see
  docs/coding_decisions.md, 2026-09-30, for the full reasoning (confirmed
  with the user, not assumed). `ucdp_conflict_intensity` is the one
  exception within `ucdp_conflict`'s own output: it stays blank (not `0`)
  whenever there's no conflict that year, since 1=minor/2=war isn't a scale
  with a meaningful zero. The UCDP source (`UcdpPrioConflict_v26_1.csv`,
  the Armed Conflict Dataset only -- not the Georeferenced Event Dataset)
  has no battle-death count column at all, so a `ucdp_conflict_deaths`
  variable is not built, rather than constructed as an unsupported proxy.
  The banking-crises source has no currency-crisis or sovereign-debt-crisis
  data either -- only `banking_crisis` is built.

**Missing years are left null, never interpolated or carried forward**
(user's own confirmed choice, 2026-09-27) -- a gap year for a slow-moving
index like V-Dem or LGBTI is still blank, not the prior year's value.

Usage:  python3 scripts/build_control_variables.py
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _panel import EXTRACTED_DIR, MAX_YEAR, MIN_YEAR, REPO, REPORTS_DIR, write_csv  # noqa: E402
from _reference import ISO3_CODES, iso3_from_name  # noqa: E402
from components.mandate import _in_closed_list, load_eu_membership  # noqa: E402

CONTROL_VARS_REPO = REPO.parent / "Control variables"
DATASETS = CONTROL_VARS_REPO / "datasets"
TARGET = EXTRACTED_DIR / "control_variables.csv"

FINAL_DATASET_REPO = REPO.parent / "Final dataset"
WB_REGION_METADATA_CSV = (
    FINAL_DATASET_REPO / "Datasets" / "API_SP.POP.TOTL_DS2_en_csv_v2_430592"
    / "Metadata_Country_API_SP.POP.TOTL_DS2_en_csv_v2_430592.csv"
)

_YEAR_RANGE = range(MIN_YEAR, MAX_YEAR + 1)


def _resolve(name: str, fixups: dict[str, str]) -> str | None:
    iso3 = iso3_from_name(fixups.get(name, name))
    return iso3 or None


# ---------------------------------------------------------------------------
# WDI (two custom extracts)
# ---------------------------------------------------------------------------

_WDI_YEAR_RE = re.compile(r"^(\d{4}) \[YR\d{4}\]$")


def _wdi(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="latin-1")
    df = df[df["Series Code"].notna()]  # drops the trailing "Data from database..." footer rows
    df = df[df["Country Code"].isin(ISO3_CODES)]
    year_cols = [c for c in df.columns if _WDI_YEAR_RE.match(c)]
    long = df.melt(
        id_vars=["Series Code", "Country Code"], value_vars=year_cols,
        var_name="year_col", value_name="value",
    )
    long["year"] = long["year_col"].str.extract(_WDI_YEAR_RE)[0].astype(int)
    long["value"] = pd.to_numeric(long["value"], errors="coerce")  # ".." -> NaN
    long = long.rename(columns={"Country Code": "iso3", "Series Code": "series"})
    long["series"] = "wdi_" + long["series"].str.replace(r"[.\s]", "_", regex=True).str.lower()
    wide = long.pivot_table(index=["iso3", "year"], columns="series", values="value", aggfunc="first")
    return wide.reset_index()


def wdi() -> pd.DataFrame:
    paths = list((DATASETS / "P_Data_Extract_From_World_Development_Indicators").glob("*_Data.csv"))
    paths += list((DATASETS / "P_Data_Extract_From_World_Development_Indicators population").glob("*_Data.csv"))
    # GDP PPP per capita, current international $ (NY.GDP.PCAP.PP.CD) --
    # added 2026-09-30. This is the current-price series; no constant-price
    # (NY.GDP.PCAP.PP.KD) series is present in any WDI extract this project
    # has, so current-price is used as provided (docs/coding_decisions.md,
    # 2026-09-30) rather than substituted for a series that isn't there.
    paths += list((DATASETS / "P_Data_Extract_From_World_Development_Indicators GDP ppp per capita")
                   .glob("*_Data.csv"))
    if not paths:
        return pd.DataFrame(columns=["iso3", "year"])
    frames = [_wdi(p) for p in paths]
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on=["iso3", "year"], how="outer")

    # Three hand-named derived variables (2026-09-30), clearer than the raw
    # wdi_<series-code> style -- plain arithmetic on columns already above,
    # so a missing operand propagates to NaN on its own; nothing is zero-
    # filled. np.log guards against a literal -inf from a non-positive input
    # rather than letting one slip into the panel silently.
    if "wdi_sp_pop_totl" in out.columns:
        pop = out["wdi_sp_pop_totl"].where(out["wdi_sp_pop_totl"] > 0)
        out["log_population"] = np.log(pop)
    if "wdi_ny_gdp_pcap_pp_cd" in out.columns:
        gdp_pc = out["wdi_ny_gdp_pcap_pp_cd"].where(out["wdi_ny_gdp_pcap_pp_cd"] > 0)
        out["log_gdp_ppp_per_capita"] = np.log(gdp_pc)
    if "wdi_ne_exp_gnfs_zs" in out.columns and "wdi_ne_imp_gnfs_zs" in out.columns:
        out["trade_openness"] = out["wdi_ne_exp_gnfs_zs"] + out["wdi_ne_imp_gnfs_zs"]

    return out


# ---------------------------------------------------------------------------
# RSF Press Freedom Index (one file per year, two methodology eras)
# ---------------------------------------------------------------------------

def rsf() -> pd.DataFrame:
    directory = DATASETS / "RSF - Press Freedom Index"
    if not directory.is_dir():
        return pd.DataFrame(columns=["iso3", "year"])
    rows: list[dict] = []
    for path in sorted(directory.glob("*.csv")):
        if "(1)" in path.stem:  # duplicate download, byte-identical to the non-suffixed file
            continue
        year = int(path.stem)
        if year not in _YEAR_RANGE:
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):  # UTF-8 BOM; the rest of the file is latin-1 (accented names)
            raw = raw[3:]
        df = pd.read_csv(io.BytesIO(raw), sep=";", decimal=",", encoding="latin-1")
        if year <= 2021:
            score_col = "Score N"  # lower = better, this era's own scale
            for _, r in df.iterrows():
                if pd.isna(r.get("ISO")):
                    continue
                rows.append({"iso3": r["ISO"], "year": year,
                             "press_freedom_score_legacy_2002_2021": r.get(score_col)})
        else:
            for _, r in df.iterrows():
                if pd.isna(r.get("ISO")):
                    continue
                rows.append({"iso3": r["ISO"], "year": year,
                             "press_freedom_score_2022_on": r.get("Score")})
    if not rows:
        return pd.DataFrame(columns=["iso3", "year"])
    return pd.DataFrame(rows).groupby(["iso3", "year"], as_index=False).first()


# ---------------------------------------------------------------------------
# Global Restrictions on Religion (Pew)
# ---------------------------------------------------------------------------

_RELIGION_FIXUPS = {
    "Ivory Coast": "Cote d'Ivoire", "Taiwan": "Taiwan, China",
    "Palestinian territories": "Palestine", "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Republic of the Congo": "Congo", "Laos": "Lao PDR",
    "Federated States of Micronesia": "Micronesia (Federated States of)",
    "South Korea": "Korea, Rep.",
}


def religion() -> pd.DataFrame:
    path = (DATASETS / "Global-Restrictions-on-Religion-2007-2022-Dataset"
            / "PublicDataset_ReligiousRestrictions_2007to2022.csv")
    if not path.is_file():
        return pd.DataFrame(columns=["iso3", "year"])
    df = pd.read_csv(path, encoding="latin-1")
    df["iso3"] = df["Ctry_EditorialName"].apply(lambda n: _resolve(n, _RELIGION_FIXUPS))
    df = df[df["iso3"].notna()]
    df["year"] = df["Question_Year"].astype(int)
    out = df[["iso3", "year", "GRI", "SHI"]].rename(
        columns={"GRI": "religion_government_restrictions_index", "SHI": "religion_social_hostilities_index"}
    )
    return out.groupby(["iso3", "year"], as_index=False).first()


# ---------------------------------------------------------------------------
# V-Dem
# ---------------------------------------------------------------------------

_VDEM_COLUMNS = [
    "v2x_polyarchy",       # electoral democracy index
    "v2x_libdem",          # liberal democracy index -- the "liberal" control
    "v2x_partipdem",       # participatory democracy index
    "v2x_delibdem",        # deliberative democracy index
    "v2x_egaldem",         # egalitarian democracy index
    "v2x_civlib",          # civil liberties index
    "v2x_clphy",           # physical violence civil liberties
    "v2x_freexp_altinf",   # freedom of expression and alternative information
    "v2x_corr",            # political corruption index
    "v2x_rule",            # rule of law index
    "v2x_gender",          # women's political empowerment index
]


def vdem() -> pd.DataFrame:
    path = DATASETS / "V-Dem-CY-FullOthers-v16_dta" / "V-Dem-CY-Full+Others-v16.dta"
    if not path.is_file():
        return pd.DataFrame(columns=["iso3", "year"])
    df = pd.read_stata(path, columns=["country_text_id", "year", *_VDEM_COLUMNS], convert_categoricals=False)
    df = df[df["country_text_id"].isin(ISO3_CODES)]
    df["year"] = df["year"].astype(int)
    df = df[df["year"].isin(_YEAR_RANGE)]
    df = df.rename(columns={"country_text_id": "iso3", **{c: f"vdem_{c}" for c in _VDEM_COLUMNS}})
    return df.groupby(["iso3", "year"], as_index=False).first()


# ---------------------------------------------------------------------------
# PLAD (leader-spell data, reduced to "leader in office as of 31 December")
# ---------------------------------------------------------------------------

def plad() -> pd.DataFrame:
    path = DATASETS / "dataverse_files (1)" / "PLAD_April_2024.dta"
    if not path.is_file():
        return pd.DataFrame(columns=["iso3", "year"])
    df = pd.read_stata(
        path, columns=["idacr", "startyear", "endyear", "gender", "ethnicity1", "geoname"],
        convert_categoricals=False,
    )
    df = df[df["idacr"].isin(ISO3_CODES)]
    df["endyear"] = df["endyear"].fillna(MAX_YEAR)
    rows: list[dict] = []
    for _, r in df.iterrows():
        start, end = int(r["startyear"]), int(r["endyear"])
        for year in range(max(start, MIN_YEAR), min(end, MAX_YEAR) + 1):
            rows.append({
                "iso3": r["idacr"], "year": year,
                "leader_gender": r.get("gender"),
                "leader_ethnicity": r.get("ethnicity1"),
                "leader_birthplace": r.get("geoname"),
            })
    if not rows:
        return pd.DataFrame(columns=["iso3", "year"])
    # A leader who left partway through a year and one who arrived the same
    # year both claim it -- keep the incumbent as of year-end (the later
    # start date), not the first row seen.
    out = pd.DataFrame(rows)
    out = out.sort_values(["iso3", "year"]).groupby(["iso3", "year"], as_index=False).last()
    return out


# ---------------------------------------------------------------------------
# LGBTI Policy Index
# ---------------------------------------------------------------------------

def lgbti() -> pd.DataFrame:
    path = DATASETS / "wta9p-osfstorage-archive" / "LGBTI_Composite_Index.csv"
    if not path.is_file():
        return pd.DataFrame(columns=["iso3", "year"])
    df = pd.read_csv(path)
    df = df[df["ISO"].isin(ISO3_CODES)]
    df["year"] = df["Year"].astype(int)
    df = df[df["year"].isin(_YEAR_RANGE)]
    out = df[["ISO", "year", "Progressive_Score", "Regressive_Score", "Composite_Index"]].rename(
        columns={"ISO": "iso3", "Progressive_Score": "lgbti_progressive_score",
                 "Regressive_Score": "lgbti_regressive_score", "Composite_Index": "lgbti_composite_index"}
    )
    return out.groupby(["iso3", "year"], as_index=False).first()


# ---------------------------------------------------------------------------
# UN Tourism (Macroeconomic, Employment aggregate, SDG)
# ---------------------------------------------------------------------------

_UN_TOURISM_FIXUPS = {
    "China, Hong Kong Special Administrative Region": "Hong Kong, China",
    "China, Macao Special Administrative Region": "Macao",
    "Republic of Korea": "Korea, Rep.",
    "Republic of Moldova": "Moldova",
    "State of Palestine": "Palestine",
}


def _un_tourism_indicator(path: Path, indicator_code: str, column: str) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=["iso3", "year"])
    df = pd.read_excel(path, sheet_name="Data")
    df = df[df["indicator_code"] == indicator_code]
    df["iso3"] = df["reporter_area_label"].apply(lambda n: _resolve(n, _UN_TOURISM_FIXUPS))
    df = df[df["iso3"].notna()]
    df["year"] = df["year"].astype(int)
    df = df[df["year"].isin(_YEAR_RANGE)]
    out = df[["iso3", "year", "value"]].rename(columns={"value": column})
    return out.groupby(["iso3", "year"], as_index=False).first()


def un_tourism() -> pd.DataFrame:
    macro = _un_tourism_indicator(
        DATASETS / "Bulk" / "05_Macroeconomic" / "UN_Tourism_8_9_1_TDGDP_05_2026.xlsx",
        "ST_GDP_ZS", "tourism_gdp_share_pct",
    )
    sdg = _un_tourism_indicator(
        DATASETS / "Bulk" / "07_SDGs" / "UN_Tourism_12_b_1_TSA_SEEA_03_2026.xlsx",
        "ST_EEV_ACCSEEA", "tourism_seea_accounting_adopted",
    )
    employment = _un_tourism_indicator(
        DATASETS / "Bulk" / "06_Employment" / "UN_Tourism_8_9_2_employed_persons_06_2026.xlsx",
        "EMPL_TOTL_TOTL_TOTL_TOTL_PRSN", "tourism_employment_total_persons",
    )
    out = macro
    for f in (sdg, employment):
        out = out.merge(f, on=["iso3", "year"], how="outer") if not out.empty else f
    return out


# ---------------------------------------------------------------------------
# EU membership (closed roster -- every country gets a confident 1/0)
# ---------------------------------------------------------------------------

def eu_member() -> pd.DataFrame:
    eu_spells = load_eu_membership()
    rows = [
        {"iso3": iso3, "year": year, "eu_member": int(_in_closed_list(iso3, year, eu_spells))}
        for iso3 in sorted(ISO3_CODES)
        for year in _YEAR_RANGE
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# World Bank region classification (static per country)
# ---------------------------------------------------------------------------

def wb_region() -> pd.DataFrame:
    if not WB_REGION_METADATA_CSV.is_file():
        return pd.DataFrame(columns=["iso3", "year"])
    df = pd.read_csv(WB_REGION_METADATA_CSV, encoding="utf-8-sig")
    df = df.rename(columns={"Country Code": "iso3", "Region": "wb_region"})
    df = df[df["iso3"].isin(ISO3_CODES) & df["wb_region"].notna() & (df["wb_region"] != "")]
    df = df[["iso3", "wb_region"]].drop_duplicates(subset=["iso3"])
    years = pd.DataFrame({"year": list(_YEAR_RANGE)})
    return df.merge(years, how="cross")


def _report_unresolved(report_path: Path, names: list[str], label: str) -> None:
    """A name that didn't resolve to an ISO3 code is dropped from the
    source, never guessed -- but always written here so it's visible,
    matching this project's `shareholders_panel_conflicts.csv`-style
    precedent for "reported, not silently dropped"."""

    write_csv(report_path, ["name", "note"], [{"name": n, "note": label} for n in names])


# ---------------------------------------------------------------------------
# UCDP/PRIO Armed Conflict Dataset v26.1 -- closed roster within the
# source's own coverage window (1946-2025). See the module docstring above
# and docs/coding_decisions.md, 2026-09-30, for the full reasoning.
# ---------------------------------------------------------------------------

_UCDP_MAX_YEAR = 2025  # the source's own documented coverage ceiling
UCDP_UNRESOLVED_REPORT = REPORTS_DIR / "ucdp_unresolved.csv"

_UCDP_FIXUPS = {
    "Cambodia (Kampuchea)": "Cambodia",
    "DR Congo (Zaire)": "Congo, Dem. Rep.",
    "Myanmar (Burma)": "Myanmar",
    "Russia (Soviet Union)": "Russia",
    "Yemen (North Yemen)": "Yemen, Rep.",
    "Ivory Coast": "Cote d'Ivoire",  # same fixup as religion()'s own
}


def ucdp_conflict() -> pd.DataFrame:
    path = DATASETS / "UcdpPrioConflict_v26_1.csv"
    if not path.is_file():
        return pd.DataFrame(columns=["iso3", "year"])
    df = pd.read_csv(path)
    df = df[df["year"].between(MIN_YEAR, _UCDP_MAX_YEAR)]

    # `location` is comma-separated for interstate conflicts (e.g. "India,
    # Pakistan"); every listed country is credited with the conflict --
    # the user's own confirmed choice, 2026-09-30. UCDP's codebook is
    # explicit that `location` names the contesting government(s), not
    # necessarily where fighting physically occurred; this ambiguity only
    # touches the ~4% of rows that are interstate (type_of_conflict == 2)
    # -- the other ~96% (intrastate/internationalized-intrastate) name
    # exactly one country, a reliable match for "conflict in that country."
    exploded = df.assign(_location=df["location"].str.split(",")).explode("_location")
    exploded["_location"] = exploded["_location"].str.strip()
    exploded["iso3"] = exploded["_location"].apply(lambda n: _resolve(n, _UCDP_FIXUPS))
    unresolved = sorted(exploded.loc[exploded["iso3"].isna(), "_location"].dropna().unique())
    exploded = exploded[exploded["iso3"].notna()]

    # A country can have more than one concurrent conflict in the same
    # year -- aggregated as "any reached war intensity" / "the worst
    # intensity seen that year," not summed or averaged.
    per_year = exploded.groupby(["iso3", "year"], as_index=False).agg(
        ucdp_war=("intensity_level", lambda s: int((s == 2).any())),
        ucdp_conflict_intensity=("intensity_level", "max"),
    )
    per_year["ucdp_armed_conflict"] = 1

    grid = pd.DataFrame(
        [(iso3, year) for iso3 in sorted(ISO3_CODES) for year in range(MIN_YEAR, _UCDP_MAX_YEAR + 1)],
        columns=["iso3", "year"],
    )
    out = grid.merge(per_year, on=["iso3", "year"], how="left")
    # Closed roster for the two binary flags: confident 0, not blank, when
    # no conflict-year row exists for that (iso3, year). `ucdp_conflict_
    # intensity` is left as-is (NaN) in that case -- see module docstring.
    out["ucdp_armed_conflict"] = out["ucdp_armed_conflict"].fillna(0).astype(int)
    out["ucdp_war"] = out["ucdp_war"].fillna(0).astype(int)

    if unresolved:
        _report_unresolved(UCDP_UNRESOLVED_REPORT, unresolved, "ucdp location token")

    return out[["iso3", "year", "ucdp_armed_conflict", "ucdp_war", "ucdp_conflict_intensity"]]


# ---------------------------------------------------------------------------
# Systemic banking crises (Laeven & Valencia 2026, IMF WP/26/94) -- closed
# roster within the source's own coverage window (1970-2025), same
# reasoning as ucdp_conflict() above.
# ---------------------------------------------------------------------------

_BANKING_CRISIS_MAX_YEAR = 2025  # source's own documented coverage: "1970-2025"
BANKING_CRISES_UNRESOLVED_REPORT = REPORTS_DIR / "banking_crises_unresolved.csv"

_BANKING_CRISIS_FIXUPS: dict[str, str] = {
    "Korea": "Korea, Rep.",              # the source's own banking-crisis literature means South Korea here
    "Republic of Congo": "Congo",        # Congo-Brazzaville; distinct from "DR Congo" (Congo, Dem. Rep.)
}

_FOOTNOTE_SUFFIX_RE = re.compile(r"\s*\d+/\s*$")  # strips trailing "N/" footnote refs, e.g. "Argentina 5/"


def _clean_banking_crisis_token(value: object) -> str:
    return _FOOTNOTE_SUFFIX_RE.sub("", str(value)).strip()


def banking_crisis() -> pd.DataFrame:
    path = DATASETS / "SYSTEMIC_BANKING_CRISES_DATABASE_2026.xlsx"
    if not path.is_file():
        return pd.DataFrame(columns=["iso3", "year"])
    df = pd.read_excel(path, sheet_name="Crisis Resolution and Outcomes")[["Country", "Start", "End"]].copy()
    df = df[df["Start"].notna()]  # drops the trailing footnote-text/blank rows at the sheet's end

    df["Country"] = df["Country"].apply(_clean_banking_crisis_token)
    df["End"] = pd.to_numeric(df["End"].apply(_clean_banking_crisis_token), errors="coerce")
    df["Start"] = pd.to_numeric(df["Start"], errors="coerce")
    df = df[df["Start"].notna()]
    # A handful of rows have no End (still ongoing at publication) -- capped
    # at the source's own coverage ceiling, never extrapolated past it.
    df["End"] = df["End"].fillna(_BANKING_CRISIS_MAX_YEAR)

    df["iso3"] = df["Country"].apply(lambda n: _resolve(n, _BANKING_CRISIS_FIXUPS))
    unresolved = sorted(df.loc[df["iso3"].isna(), "Country"].unique())
    df = df[df["iso3"].notna()]

    rows: list[dict] = []
    for _, r in df.iterrows():
        start = max(int(r["Start"]), MIN_YEAR)
        end = min(int(r["End"]), _BANKING_CRISIS_MAX_YEAR)
        for year in range(start, end + 1):
            rows.append({"iso3": r["iso3"], "year": year})
    crisis_years = (
        pd.DataFrame(rows).drop_duplicates() if rows else pd.DataFrame(columns=["iso3", "year"])
    )
    crisis_years["banking_crisis"] = 1

    grid = pd.DataFrame(
        [(iso3, year) for iso3 in sorted(ISO3_CODES) for year in range(MIN_YEAR, _BANKING_CRISIS_MAX_YEAR + 1)],
        columns=["iso3", "year"],
    )
    out = grid.merge(crisis_years, on=["iso3", "year"], how="left")
    out["banking_crisis"] = out["banking_crisis"].fillna(0).astype(int)

    if unresolved:
        _report_unresolved(BANKING_CRISES_UNRESOLVED_REPORT, unresolved, "banking-crisis country name")

    return out[["iso3", "year", "banking_crisis"]]


# ---------------------------------------------------------------------------

def main() -> int:
    if not DATASETS.is_dir():
        print(f"error: {DATASETS} does not exist.", file=sys.stderr)
        return 2

    tables = [wdi(), rsf(), religion(), vdem(), plad(), lgbti(), un_tourism(), eu_member(), wb_region(),
              ucdp_conflict(), banking_crisis()]
    merged = tables[0]
    for t in tables[1:]:
        if t.empty:
            continue
        merged = merged.merge(t, on=["iso3", "year"], how="outer") if not merged.empty else t

    merged = merged.sort_values(["iso3", "year"])
    merged.to_csv(TARGET, index=False)

    print(f"{len(merged)} country-year rows, {len(merged.columns) - 2} control variables -> "
          f"{TARGET.relative_to(REPO)}")
    for col in merged.columns:
        if col in ("iso3", "year"):
            continue
        coverage = merged[col].notna().sum()
        print(f"  {col:45} {coverage:6} / {len(merged)} non-null")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Reviewer quick start

This is a synthetic enterprise assurance demonstration, as of **30 September 2026**. It is not Experian internal methodology.

1. Open [the eight-slide executive presentation](presentation/assurance_executive_report.pptx). Slide 6 explains sources, the processing flow, and the claim-to-evidence traceability path; each slide's Notes contains metric definitions and caveats. Keep this folder structure intact so its HTML and Tableau links resolve.
2. Download this repository folder and open [the offline HTML dashboard](html/assurance_dashboard.html). Select **Data & Metrics** for source formats, grains, numerator/denominator definitions, evidence states, validation boundaries, and design rationale. GitHub displays HTML source; it does not run this dashboard.
3. Open [the Tableau packaged workbook](tableau/assurance_dashboard.twbx) in a compatible Tableau client. **About / Data & Metrics** contains governed definitions. This workbook passed programmatic package, data, field-binding, and default-scope validation. Tableau Desktop rendering was not executed.
4. Browse [slide previews](visuals/slide-01.png), exported from the exact clean-run deck in Microsoft PowerPoint, or use the eight numbered images in `visuals/`.

## How to read the analysis

SQLite supplies enterprise reference records; JSON supplies control evidence; CSV files supply findings and management actions. Python validates, normalizes, reconciles, computes governed analytics, cross-checks Pandas and DuckDB results, and publishes one analytical truth to all three channels. The source data, calculation rules, metric contract, and reconciliation semantics are preserved by this change.

Headline counts use assurance-test grain unless their definition specifies findings or actions. Nine assurance tests include five sufficient, one partial, two insufficient, and one not-evaluable evidence result. Stale evidence is an overlapping freshness flag, not another mutually exclusive sufficiency class. Ten unmapped source records reconcile to one unmapped assurance test; these are different grains. NOT_EVALUABLE means the required basis for evaluation is unavailable, and NOT_TESTED describes mapped source records that were not evaluated. Residual risk is the existing illustrative governed classification, not a claim of real enterprise risk.

Detailed numerator, denominator, trusted population, filter scope, and limitations come from upstream explanatory metadata bound to this run's validated metrics and publication tables. Renderers do not calculate independent KPI definitions.

## Producer provenance and acceptance

Clean producer run: `20261005T175406684735Z`. Producer source commit: `c8bcb089332e19f919d200a280a837ba3a53c103`. Producer working tree: **clean (`git_dirty=false`)**. Reporting date: **2026-09-30**. The later reviewer-artifact commit publishes copies of these source-commit outputs; it does not change their producer identity.

All eight exact clean-run slides were rendered and visually inspected in Microsoft PowerPoint. PowerPoint slideshow navigation to slides 1–8 was executed; the 114 internal navigation targets and 17 external publication links passed structural validation. The eight previews were exported from that exact deck.

All 128 tests passed on the committed source. Ruff and git diff --check passed. All twelve metrics and seven publication tables match the preceding canonical run, excluding execution identity. The fail-closed presentation gate checks complete HTML records, embedded metric definitions, actual PowerPoint headlines and every slide's metric Notes.

HTML passed programmatic content, package, embedded-resource, current-run, relative-link and accessibility-structure checks. JavaScript syntax and isolated counting checks passed; these do not establish browser rendering or assistive-technology conformance. Browser interactions remain **NOT_EXECUTED**: the repository has no browser/DOM harness, and browser security policy blocks the local-file route and alternate workarounds. No runtime browser pass is claimed.

Tableau acceptance is **PROGRAMMATIC_TABLEAU PASS**: genuine Hyper data parity, TWB field/visual bindings and default scope, plus exact current TWB and Hyper bytes inside the TWBX. Tableau Desktop was **NOT_EXECUTED**.

The complete HTML subtree and all presentation-linked destinations are included. No duplicate submission ZIP is included. Generated runs remain under ignored `output/`; this folder is the deliberately curated reviewer copy. Standalone support CSVs, field dictionaries, metrics and machine-readable manifests are intentionally reproducible rather than duplicated here; the root README gives the exact locations and reproduction procedure at this producer source commit.

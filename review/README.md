# Reviewer guide

Start with the eight-slide PowerPoint, then explore HTML and Tableau before inspecting the implementation. This is a synthetic enterprise assurance demonstration as of **30 September 2026**, not Experian internal data or methodology.

## Open the artifacts

| Artifact | Exact path and purpose |
| --- | --- |
| Executive presentation | [presentation/assurance_executive_report.pptx](presentation/assurance_executive_report.pptx) — narrative, reconciliation, priorities and relative drill links. Slide 6 explains the processing flow; slide Notes provide definitions and caveats. |
| Slide previews | [visuals/](visuals/) — `slide-01.png` through `slide-08.png`, exported from the exact committed deck in Microsoft PowerPoint. View these directly on GitHub without PowerPoint. |
| HTML dashboard | [html/assurance_dashboard.html](html/assurance_dashboard.html) — offline analysis. **Data & Metrics** explains source formats, grains, definitions and validation boundaries. |
| HTML detail | [html/reports/](html/reports/) contains four reports; [html/charts/](html/charts/) contains six charts, linked from the dashboard. |
| Tableau | [tableau/assurance_dashboard.twbx](tableau/assurance_dashboard.twbx) — packaged TWB and genuine Hyper extract, with four dashboards, eleven worksheets and eight datasets. **About / Data & Metrics** provides governed definitions. |

**Download and extract the repository before opening HTML locally.** GitHub shows HTML source and does not execute the dashboard. Keep the complete `review/` folder structure intact for HTML and PowerPoint relative links. Open the TWBX in compatible Tableau software; Tableau Desktop execution has not been validated.

## Read the counts correctly

Headline counts use assurance-test grain unless defined for findings or actions. Stale evidence is an overlapping freshness flag, not another sufficiency category. Ten unmapped source records correspond to one unmapped assurance test. **NOT_EVALUABLE** means the required evaluation basis is unavailable; **NOT_TESTED** describes mapped source records that were not evaluated. Findings and management actions have separate grains.

The root README contains the full governed results, architecture, setup and reproduction procedure. Implementation is under `src/experian_workflow/`, assurance contracts under `config/assurance/`, synthetic sources under `data/source/`, and tests with independent fixtures under `tests/`.

## Provenance and validation

Artifact producer run: `20261006T015512364859Z`. Producer source commit: `bd354e4f887db3130bb62e60925f39328a5042df`. Producer working tree: **clean (`git_dirty=false`)**. Reporting date: **2026-09-30**. Subsequent documentation and artifact-publication commits do not change this producer identity.

- **128/128 tests**, Ruff and `git diff --check` passed on the producer source.
- All **12 governed metrics** and **7 publication tables** matched the preceding canonical results, excluding execution identifiers. Cross-output checks compared complete HTML records, metric definitions, PowerPoint headlines and slide Notes with the same-run publication truth.
- **PowerPoint:** eight slides rendered and visually inspected in Microsoft PowerPoint; slideshow navigation to slides 1–8 executed. All 114 internal navigation targets and 17 external publication links passed structural checks.
- **HTML:** all eleven files passed content, embedded-resource, relative-link and accessibility-structure checks.
- **Tableau:** programmatic Hyper data parity, TWB field/visual bindings, default scope and exact packaged TWB/Hyper byte identity passed.

Browser-rendered HTML/live interactions: **NOT_EXECUTED**. Tableau Desktop: **NOT_EXECUTED**. HTML structural checks do not establish runtime behaviour or assistive-technology conformance.

This folder contains exactly 22 reviewer files. Supporting tables, metric JSON, field dictionaries and manifests are available by reproducing the producer source commit; their generated locations are documented in the root README. They are omitted here to avoid duplicate analytical copies.

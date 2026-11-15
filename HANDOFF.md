# Handoff: IronViz 2026 analysis (session of 2026-11-14)

**Read first:** `instructionsprocess.md` (agent rules + rubric) → `process-log.md` sections **B0** (decision register), **B0a** (headline findings), **B0b** (proxies/swappable inputs). Everything below is detailed there.

## Ground rules from the user
- **Ask before any major decision** (story, personas, data, methods) and **before making any visuals**. Offer options + a recommendation.
- **Log every human decision** in `process-log.md` B0 as a new `D#` row (open questions as `P#`); also add a narrative row to B6.
- Never fabricate numbers; flag anything unverified or proxied in B0b.
- Deadline: competition submission **Sat Nov 14, 2026, 11:59 PM EST**. Deliverables: (1) PDF/PNG visual export, (2) source code/repo, (3) written AI-use documentation.

## Project
CMU Student IronViz, "Intelligence at Scale". Question: *what AI recommendations should CMU implement, per campus persona, to lower cost and resource use?* Audience: **mixed campus** (dean, student, IT admin) — plain language.

## Data & pipeline (all run from repo root with `py`; pandas installed)
| Script | Output (in `data-clean/`) |
|---|---|
| `scripts/01_clean_harmonize.py` | `calls_unified.csv` (202,650 calls, OpenAI+Gemini harmonized via the data dictionary crosswalk; 0 rows dropped; QA in `qa_report.txt`) |
| `scripts/02_tenant_summary.py` | `tenant_summary.csv` |
| `scripts/03_cost.py [config/pricing_X.csv]` | `calls_costed__*.csv`, `cost_by_tenant__*.csv` (swappable pricing) |
| `scripts/04_small_differences.py` | `small_differences.csv` (42 tests among the 4 look-alike tenants) |
| `scripts/06_carbon.py` | `calls_costed_carbon__*.csv`, `carbon_by_tenant__*.csv` (low/central/high Wh + gCO2e) |
| `scripts/05_local_best.py` (run after 06) | `persona_metrics.csv`, `local_best_ranking.csv`, `outliers_vs_local_good.csv` |
| `scripts/07_scenarios.py` (after 05) | `scenarios_by_tenant__*.csv`, `scenario_errors_avoided__*.csv`, `scenario_route_ceiling.csv`. Local good = same-provider average of the other teams (D24); global good = per-unit steps, no targets (D23) |
| `scripts/08_guidance_check.py` | `guidance_check.csv`: each team vs local good and cited provider guidance (`config/guidance_sources.csv`, D25; see process-log B0c) |
Configs: `config/pricing_list.csv`, `config/energy_benchmarks.csv`, `config/carbon_params.csv` (see `config/README.md`).

## Decisions made (D1–D15, summary)
6 tenants kept separate with merge labels (D2, labels confirmed D15) · mixed audience (D3) · ignore the competition deck's anomaly claims — the release has none (D6) · students = Sandbox + R&D as a labeled assumption (D7) · **story: Dev & Sandbox are outliers; best of the other 4 = "local good"; "global good" from external best practices + token efficiency (D11)** · list prices, swappable for CMU rates (D9) · price verification on hold (D13) · carbon = published LLM benchmarks (Jegham et al. 2025 + Google 2025) × CodeCarbon grid factors, as a range; the HF dataset is context only (D14).

## Key findings (synthetic data; carbon estimated)
- Dev/Sandbox vs local good: 1.5–2.0× cost/call, 1.2–1.5× energy/call, 1.9–3.8× prompt size, cache share 2.5% vs 22.6%, 400-error rate 6% vs 1.1%.
- The other 4 tenants are statistically indistinguishable; Core Production Services = tie-break local good.
- o1-preview: ~10% of OpenAI calls → 60–69% of OpenAI cost, ~30–35% of energy.
- 30-day total: $5,711; 277/387/496 kWh; 26/135/292 kg CO2e (low/central/high).
- Output tokens drive energy → caching is mainly a **cost** lever; model tier + output length are the **energy** levers.
- No time-of-day, daily-trend, or retry-storm signal (synthetic uniformity) — don't chart those.
- All models in the data are retired/retiring as of 2026-11-14 (o1 shut down Oct 23 2026; gpt-4o/mini shut down Jan 14 2027).

## Resolved this session
- **D16 (P5):** global good = what-if scenarios → `scripts/07_scenarios.py` + `config/scenario_params.csv` → `data-clean/scenarios_by_tenant__pricing_list.csv`, `scenario_errors_avoided__pricing_list.csv`. Results in B0a #9; assumptions X16–X19 in B0b.
- **D17 (P6):** use the data's model names, each with a purpose label (reasoning / frontier / small-fast).
- **D18:** the models are outdated on purpose (a lesson in model drift). See the "Lens" note in `instructionsprocess.md` §1: habits vs expiring details (shelf-life tags), a purpose → current-model table, persona roles, and dated charts with ranges.

## Next
- **P3 — (deferred)** user to verify o1-preview, gemini-1.5-pro, flash-cached prices.
- User may want to review scenario thresholds (50% cache, 50% reasoning routing, p75 output cap).
- **Propose 2–3 chart options per insight and ask before making any visual** (see `instructionsprocess.md` §3 table). Then fill B5 (viz decisions) and B8 (recommendations by persona).

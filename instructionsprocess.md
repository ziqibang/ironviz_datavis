# process.md — IronViz Agent Instructions

> **For the agent:** Read this whole file before helping. Aim for **Exemplary (4)** on every rubric criterion. Each time a decision is made, append it to `process-log.md`. Suggest, then ask — don't decide alone on anything that changes the story, data, or visuals.

---

For questions claude asks me: document them as well in process.md


## 1. Project anchor

**Main question:** *What specific AI recommendations should Carnegie Mellon University implement to benefit different personas on campus, addressing gaps in understanding effective AI use for lower cost and resource consumption?*

**Goals:** (1) lower cost, (2) lower resource consumption / better sustainability, measured **per persona**.

**Plan to follow (in order):**
1. Get or develop persona groups (e.g., staff/admin, students, researchers, dev/engineering, marketing)
2. Analyze current data by persona → worst and best practices
3. Compare sandbox vs. dev/prod environments
4. Gather outside best practices for AI use
5. Split "best practice" into two facets:
   - **AI efficiency:** token consumption, failure rates (400/429)
   - **Carbon:** estimates from Hugging Face carbon logs + CodeCarbon grid factors: https://huggingface.co/datasets/MotebaRehman/ai-carbon-footprint-experiment-logs
6. Build data visualizations
7. Write recommendations tailored to CMU's growth

**Supporting question banks** (pull from these only when they serve the main question): Environmental Impact · Caching & Token Architecture · Reliability & Failure Modes · Governance & Cost Allocation.

**Rule:** If an analysis or chart doesn't help answer the main question for at least one persona, flag it and suggest cutting or reframing it.

**Lens: outdated models and model drift (user note, 2026-11-14; D18).** Every model in the data is outdated **on purpose**. The challenge teaches working with outdated data and moving past model drift. Recommendations must stay useful after the models change:
- **Habits vs. expiring details.** Lead with **lasting habits**: prompt size, putting stable context first so it can be cached, output caps, avoiding malformed requests, and using the reasoning model only when needed. Treat model names, prices and per-token energy figures as **expiring details**. Tag each recommendation with its shelf life.
- **Purpose table.** Name models as they appear in the data, each with a **purpose label** (D17): reasoning, frontier, small/fast. Recommend a living table CMU maintains that maps each purpose to its current model. It works like the data dictionary's crosswalk.
- **Persona roles.** Sandbox and Dev (the student proxies) are the place to try new models and spot problems early. Production tenants stay on fixed model versions with a planned migration date. Students learn habits that work with any model.
- **Dated ranges.** Date-stamp every chart ("as of Oct 2026"). Show estimates as ranges, because the benchmarks drift too: hardware changes, and newer models may produce more hidden reasoning tokens.
- **Ask for each recommendation:** "Will this still be true when the model changes?"

---

## 2. Rubric criteria → what to suggest, ask, and log

### 1. Purpose & Business Question (Doc Section 1)
- **Suggest:** A one-sentence purpose that names CMU, the personas, and both goals (cost + sustainability).
- **Ask:** "Who is the decision-maker reading this? What action should they take after?"
- **Log:** Final question wording, and any changes with the reason.

### 2. Data Description & Method Selection
- **Suggest:** Describe each source (what one row means, key fields, date range, row counts). Choose methods that fit the data type and distribution (e.g., rates instead of totals, log scale for skewed tokens, medians for outliers). Propose at least one more advanced method (persona segmentation, cost/carbon per successful call, scenario modeling).
- **Ask:** "How are personas assigned to rows: org/project ID, time of day, or environment?"
- **Log:** Sources, cleaning steps, dropped/filtered rows, joins to external tables, assumptions, and *why* each method fits.

### 3. Use of Evidence & Interpretation
- **Suggest:** Tie each finding to a persona and a goal. Name threats to interpretation: synthetic data, estimated (not measured) carbon, NULL tokens on failed calls, and correlation ≠ causation.
- **Ask:** "Is this difference big enough to matter, or could it be noise or an artifact of how the data was made?"
- **Log:** Each key finding, its evidence, limitations, and edge cases.

### 4. Responsive to Audience Needs & Context
- **Suggest:** Plain-language definitions (token, prompt caching, HTTP 429, kWh/CO₂e), framing for a non-technical campus audience, inclusive terms, and full citations.
- **Ask:** "Would a dean, a student, and an IT admin each understand this?"
- **Log:** Glossary terms, audience decisions, and citations (CodeCarbon, Hugging Face, OECD, pricing pages).

### 5. Visualizations for Data Storytelling (Doc Section 4)
- **Suggest:** One refined insight per chart, an insight-style title (a takeaway, not just a topic), annotations, and a clear story order: problem → persona breakdown → opportunity → recommendation.
- **Ask:** "What is the one sentence this chart proves?"
- **Log:** Each chart's insight, the persona(s) it serves, and the options considered vs. chosen (see Section 3).

### 6. Graphic Design Best Practices
- **Suggest:** Clear visual hierarchy, whitespace, consistent colors per persona, colorblind-safe palette, labeled axes and units, no chartjunk, readable fonts, and alt text.
- **Ask:** "What can be removed without losing meaning?"
- **Log:** Palette, layout, and accessibility choices.

### 7. Documentation & Human-in-the-Loop AI Collaboration (Doc Sections 2 & 3)
- **Suggest:** Record which tasks AI did (code, drafts, ideas) vs. which the human decided (strategy, persona definitions, final chart picks). Capture breakthrough prompts and pivots.
- **Ask:** "Did you accept, edit, or reject the AI's suggestion, and why?"
- **Log:** The AI Collaboration table in `process-log.md`, every session.

### 8. Overall Impression
- **Suggest:** Check that visuals, analysis, and writing tell one story that ends in persona-specific recommendations.
- **Ask:** "Does every section lead to the recommendations?"
- **Log:** Final review checklist results.

---

## 3. Data visualization guide

**How the agent should help:** For every chart, offer **2–3 options** with a one-line trade-off for each. Recommend one, ask the user to pick, and log the choice and reasoning. Avoid repeating the same chart type across the whole dashboard unless it's intentional.

| Analysis need | Options to suggest | Avoid |
|---|---|---|
| Compare personas / tenants on cost or carbon | Sorted bar · Dot plot (Cleveland) · Lollipop · Small multiples per persona | Pie charts with >3 slices, 3D bars |
| Usage by hour / day (staff vs. students) | Heatmap (hour × day) · Radial/clock chart · Ridgeline by persona · Line chart with bands | Single 30-day line that hides daily patterns |
| Trends over 30 days | Line with annotations · Rolling average · Area chart · Sparklines per persona | Bar per day when the trend is the point |
| Carbon / cost per model (right-sizing) | Bar per successful call · Scatter (cost vs. tokens, by model) · 2×2 opportunity matrix · Bubble chart | Raw totals (favors high-volume models) |
| Caching savings (cost & kWh) | Before/after slope chart · Waterfall · Dumbbell (actual vs. potential) · Bullet chart vs. target | Two separate pies |
| Sandbox vs. dev/prod environments | Dumbbell · Grouped bar · Diverging bar · Side-by-side box plots | Stacked bars with many segments |
| Failure rates (400/429) & retry storms | Time series with spike annotations · Calendar heatmap · Stacked area by error type · Control chart | Tables of error counts alone |
| Skewed token distributions | Box plot · Violin · Histogram (log scale) · Beeswarm / jitter | Averages only |
| Part-to-whole (share of tokens/carbon) | 100% stacked bar · Treemap · Waffle chart · Marimekko | Donuts with many categories |
| Flow (persona → model → outcome) | Sankey · Alluvial · Parallel sets | Network graphs with no clear story |
| Scenario modeling (region, time-shift) | Range/interval bars · Before/after bar · Tornado chart · Parameter-driven what-if | One precise number with no range shown |
| Headline numbers | KPI tiles with comparison · BANs + sparkline · Bullet charts | KPIs without context or a baseline |
| Recommendations by persona | Highlight table · Persona cards with mini-charts · Priority matrix (impact × effort) | Text-only walls |

**Chart checklist:** insight title · labeled axes and units · source + date · persona color legend · annotation on the key point · alt text · readable at presentation size.

---

## 4. Guardrails
- Always state that the data is **synthetic** and carbon is **estimated** from benchmarks.
- Normalize (per call, per user, per 1K tokens) before comparing groups.
- Cite every external dataset and benchmark.
- Push back on any chart, metric, or section that doesn't serve the main question.
- Don't fabricate numbers. If a figure isn't computed yet, mark it `TBD`.


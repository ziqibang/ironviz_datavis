"""Chart E8 (D26, revised D27): "Out of every 100" - how OpenAI requests, cost and energy split across the
three model types in the data: reasoning (o1-preview), frontier (gpt-4o) and small/fast (gpt-4o-mini).

Reads data-clean/calls_costed_carbon__<pricing>.csv (from 03 + 06), computes each model's share of requests, cost
and energy (rounded to whole squares with the largest-remainder method so each grid sums to exactly 100), and writes
  viz/e8_reasoning_out_of_100.html   standalone chart
  viz/e8_section.html                the same chart as a <section> fragment (pasted into the mockup comparison page)
  viz/e8_data.json                   the numbers behind the chart
Run from repo root: py scripts/09_build_e8.py [pricing_tag]      (default: pricing_list)
Data is synthetic (Oct 1-30, 2026). Energy is an ESTIMATE (central). Some prices are unverified (process-log B0b).
"""
import json
import math
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
tag = sys.argv[1] if len(sys.argv) > 1 else "pricing_list"
d = pd.read_csv(ROOT / "data-clean" / f"calls_costed_carbon__{tag}.csv",
                usecols=["provider", "model", "is_success", "cost_usd", "wh_central", "wh_low", "wh_high"])
ok = d[(d.provider == "openai") & d.is_success]
n = int(len(ok))

# order = fill order in every grid; purpose labels per D17
MODELS = [("o1-preview", "reasoning", "Reasoning model", "for multi-step problems"),
          ("gpt-4o", "frontier", "Frontier model", "for general high-quality work"),
          ("gpt-4o-mini", "small", "Small/fast model", "for routine tasks")]
g = ok.groupby("model").agg(requests=("model", "size"), cost=("cost_usd", "sum"), energy=("wh_central", "sum"))
pct = (g / g.sum() * 100).loc[[m[0] for m in MODELS]]


def squares(col):
    """Largest-remainder rounding so the three models fill exactly 100 squares."""
    raw = pct[col]
    base = raw.apply(math.floor)
    left = 100 - int(base.sum())
    for m in (raw - base).sort_values(ascending=False).index[:left]:
        base[m] += 1
    return {m: int(base[m]) for m in raw.index}


sq = {col: squares(col) for col in ("requests", "cost", "energy")}
mean = ok.groupby("model")[["cost_usd", "wh_central", "wh_low", "wh_high"]].mean()
per_req = {m: {"usd": mean.loc[m, "cost_usd"], "wh": mean.loc[m, "wh_central"],
               "wh_lo": mean.loc[m, "wh_low"], "wh_hi": mean.loc[m, "wh_high"]} for m, *_ in MODELS}
print(f"OpenAI successful requests: {n:,}")
print("Shares (%):\n", pct.round(1).to_string())
print("Squares:", sq)
print("Per request:", {m: {k: round(v, 4) for k, v in x.items()} for m, x in per_req.items()})

CSS = """
.e8 { --reasoning: #eb6834; --frontier: #2a78d6; --small: #1baf7a; --cellgap: 3px; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .e8 { --reasoning: #d95926; --frontier: #3987e5; --small: #199e70; } }
:root[data-theme="dark"] .e8 { --reasoning: #d95926; --frontier: #3987e5; --small: #199e70; }
.e8 .key { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.e8 .key > div { display: grid; grid-template-columns: 16px minmax(0, 1fr); gap: 10px; align-items: start; padding: 10px 12px; border: 1px solid var(--rule); border-radius: 8px; }
.e8 .key i { width: 16px; height: 16px; border-radius: 3px; margin-top: 3px; }
.e8 .key b { display: block; font-size: 14.5px; }
.e8 .key span { font-size: 13px; color: var(--fg2); }
.e8 .key code { font-size: 12.5px; }
.e8 .key .pr { display: block; margin-top: 4px; font-variant-numeric: tabular-nums; color: var(--fg); font-size: 13px; }
.e8 .grids { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 28px; }
.e8 .g { display: grid; gap: 10px; align-content: start; min-width: 0; }
.e8 .gt { font-family: var(--display, inherit); font-size: 18px; font-weight: 600; }
.e8 .gt small { font-family: var(--body, inherit); font-weight: 400; font-size: 13px; color: var(--muted); }
.e8 .w { display: grid; grid-template-columns: repeat(10, 1fr); gap: var(--cellgap); width: min(100%, 240px); aspect-ratio: 1; }
.e8 .w i { border-radius: 3px; }
.e8 .split { display: grid; gap: 3px; font-size: 13.5px; font-variant-numeric: tabular-nums; width: min(100%, 240px); }
.e8 .split div { display: grid; grid-template-columns: 12px minmax(0, 1fr) auto; gap: 8px; align-items: center; }
.e8 .split i { width: 12px; height: 12px; border-radius: 2px; }
.e8 .split b { font-weight: 600; }
.e8 .split .hl { font-weight: 600; }
.e8 .ann { border-left: 3px solid var(--reasoning); padding: 4px 0 4px 14px; font-size: 15.5px; max-width: 76ch; }
.e8 .habit { background: var(--chip); border-radius: 8px; padding: 12px 16px; font-size: 14.5px; max-width: 84ch; }
.e8 .habit .k { font-size: 12px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); font-weight: 600; display: block; margin-bottom: 2px; }
.e8 .foot { font-size: 12.5px; color: var(--muted); border-top: 1px solid var(--rule); padding-top: 12px; display: grid; gap: 4px; }
.e8 .foot a { color: var(--fg2); }
@media (max-width: 720px) { .e8 .grids, .e8 .key { grid-template-columns: 1fr; } }
"""

def section(extra_class="", eyebrow="Price of a habit · OpenAI teams · October 2026", tradeoffs=""):
    key = "".join(
        f'<div><i style="background:var(--{c})"></i><div><b>{lab}</b><span><code>{m}</code> · {purpose}</span>'
        f'<span class="pr">${per_req[m]["usd"]:.3f} and {per_req[m]["wh"]:.1f} Wh per request</span></div></div>'
        for m, c, lab, purpose in MODELS)
    grids = ""
    for col, word, unit in (("requests", "requests", ""), ("cost", "dollars", ""), ("energy", "watt-hours", " (estimated)")):
        cells = "".join(f'<i style="background:var(--{c})"></i>' * sq[col][m] for m, c, *_ in MODELS)
        split = "".join(f'<div class="{"hl" if c == "reasoning" else ""}"><i style="background:var(--{c})"></i>'
                        f'<span>{lab.split(" model")[0]}</span><b>{sq[col][m]}</b></div>' for m, c, lab, _ in MODELS)
        grids += (f'<div class="g"><div class="gt">Every 100 {word}<small>{unit}</small></div>'
                  f'<div class="w" aria-hidden="true">{cells}</div><div class="split">{split}</div></div>')
    r, f, s = (sq["requests"][m] for m, *_ in MODELS)
    rc, fc, scst = (sq["cost"][m] for m, *_ in MODELS)
    re_, fe, se = (sq["energy"][m] for m, *_ in MODELS)
    dr = per_req["o1-preview"]; df = per_req["gpt-4o"]
    return f"""<section class="panel e8 {extra_class}" aria-labelledby="e8-title" aria-describedby="e8-alt">
  <div>
    <div class="eyebrow">{eyebrow}</div>
    <h2 id="e8-title">Out of every 100 OpenAI requests, {r} used the reasoning model, and they ran up {rc} of every 100 dollars</h2>
  </div>
  <div class="howto"><b>How to read:</b> the three model types are compared. Each grid has 100 squares, colored by model type, so you can see how requests, cost and energy split.</div>
  <div class="key">{key}</div>
  <div class="grids">{grids}</div>
  <div class="ann">The reasoning model handled <b>{r}</b> of every 100 requests but cost <b>{rc}</b> of every 100 dollars. The small/fast model handled <b>{s}</b> requests for about <b>{scst}</b> dollar. A reasoning request cost about <b>${dr["usd"] - df["usd"]:.2f}</b> more and used <b>{dr["wh"] - df["wh"]:.1f} Wh</b> more (range {dr["wh_lo"] - df["wh_lo"]:.1f}–{dr["wh_hi"] - df["wh_hi"]:.1f}) than a frontier request.</div>
  <div class="habit"><span class="k">The habit that outlasts the model</span>Use a reasoning model for complex, multi-step problems. For everything else, OpenAI advises: <q>Speed and cost → GPT models are faster and tend to cost less</q>.</div>
  <p id="e8-alt" hidden>Three 10 by 10 grids comparing three OpenAI model types in October 2026. Requests: reasoning {r}, frontier {f}, small/fast {s}. Dollars: reasoning {rc}, frontier {fc}, small/fast {scst}. Estimated watt-hours: reasoning {re_}, frontier {fe}, small/fast {se}.</p>
  <div class="foot">
    <span><b>Data:</b> CMU IronViz synthetic telemetry, Oct 1–30, 2026; {n:,} successful requests from the three OpenAI teams (the Gemini teams have no reasoning model in the data). Squares are rounded so each grid adds to 100.</span>
    <span><b>Cost:</b> public list prices (the o1-preview price is from a third-party archive and unverified). <b>Energy:</b> estimated from Jegham et al. (2025), arXiv:2505.09598, and Elsworth et al. (2025), arXiv:2508.15734; the o1 benchmark stands in for o1-preview.</span>
    <span><b>Guidance:</b> OpenAI, <i>Reasoning best practices</i>, <a href="https://developers.openai.com/api/docs/guides/reasoning-best-practices">developers.openai.com/api/docs/guides/reasoning-best-practices</a>, accessed Nov 14, 2026. All three models have since been retired or scheduled for retirement; the habit applies to whichever models are current.</span>
  </div>
  {tradeoffs}
</section>"""


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model Types Out of 100</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600&display=swap">
<style>
:root { --bg: #ffffff; --fg: #141716; --fg2: #4d5552; --muted: #6f7874; --rule: #dfe3e1; --chip: #f1f3f2;
  --display: "Space Grotesk", "Segoe UI", system-ui, sans-serif; --body: "Inter", "Segoe UI", system-ui, sans-serif; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #161918; --fg: #eef0ef; --fg2: #c0c6c3; --muted: #959e9a; --rule: #2c3130; --chip: #202422; color-scheme: dark } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font-family: var(--body); font-size: 15px; line-height: 1.5;
  padding: 36px max(16px, env(safe-area-inset-right, 0px)) 36px max(16px, env(safe-area-inset-left, 0px)); }
.panel { max-width: 1000px; margin: 0 auto; display: grid; gap: 20px; }
.eyebrow { font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
h2 { font-family: var(--display); font-size: 28px; line-height: 1.2; font-weight: 600; margin: 4px 0 0; text-wrap: balance; max-width: 34ch; }
.howto { font-size: 14px; color: var(--fg2); }
code { font-family: ui-monospace, Consolas, monospace; }
__CSS__
</style>
</head>
<body>
__SECTION__
</body>
</html>
"""
viz = ROOT / "viz"
viz.mkdir(exist_ok=True)
(viz / "e8_reasoning_out_of_100.html").write_text(PAGE.replace("__CSS__", CSS).replace("__SECTION__", section()), encoding="utf-8")
mock_tradeoffs = """<div class="tradeoffs">
    <div><h3>Strengths</h3><ul><li>All three model types are named, colored and explained, so the comparison is explicit.</li><li>The same 100-square format shows requests, cost and energy side by side.</li><li>Shows the small/fast model doing 42% of the work for about 1% of the cost.</li></ul></div>
    <div><h3>Weaknesses</h3><ul><li>More to read than the orange-only version.</li><li>OpenAI only (Gemini has no reasoning model in the data).</li></ul></div>
  </div>"""
(viz / "e8_section.html").write_text(
    "<style>" + CSS + "</style>\n" +
    section(eyebrow="Option E8 revised · three model types compared (chosen design, D26/D27)", tradeoffs=mock_tradeoffs)
    .replace('<section class="panel e8', '<section id="opt-e8r" class="panel e8', 1), encoding="utf-8")
(viz / "e8_data.json").write_text(json.dumps({"pct": pct.round(3).to_dict(), "squares": sq, "per_request": per_req,
                                              "n_requests": n, "pricing": tag}, indent=1), encoding="utf-8")
print("Wrote viz/e8_reasoning_out_of_100.html, viz/e8_section.html, viz/e8_data.json")

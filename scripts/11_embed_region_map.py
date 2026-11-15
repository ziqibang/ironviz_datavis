"""Embed the data-center region map (P21) into the dashboard design as a static SVG section.

The map page (mockups/datacenter-map.html) draws with d3 + us-atlas at runtime. The dashboard
(dashboard-designs/Main.dc.html) is a template that can't load those, so we render the map once in
headless Chrome, take the finished <svg>, inline its CSS classes as styles, round coordinates,
and insert it as the last section (before the footer). Re-run after scripts/10 changes.

Usage (repo root):
  chrome --headless=new --allow-file-access-from-files --virtual-time-budget=8000 \
         --dump-dom "file:///<repo>/mockups/datacenter-map.html?palette=purple" > <tmp>/mapdom.html
  py scripts/11_embed_region_map.py <tmp>/mapdom.html [path/to/Main.dc.html]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dashboard-designs" / "Main.dc.html"
# optional 2nd arg: another copy of Main.dc.html to patch (e.g. the claude.ai canvas copy)
if len(sys.argv) > 2:
    DASH = Path(sys.argv[2])
START, END = "<!-- SECTION 6: WHERE TO RUN (P21) -->", "<!-- /SECTION 6 -->"

dom = Path(sys.argv[1]).read_text(encoding="utf-8")
svg = re.search(r'<svg id="map".*?</svg>', dom, re.S).group(0)

PAGE = "#FFFFFF"  # dashboard card background
CLASS = {
    "state": "fill:#e9e7e0;stroke:#ffffff;stroke-width:1.2",
    "canada": "fill:#f1f0eb;stroke:#ffffff;stroke-width:1",
    "ctry": "fill:#898781;font-size:15px;letter-spacing:.4em;font-weight:600",
    "city": f"font-size:15px;font-weight:700;fill:#1A1A1A;paint-order:stroke;stroke:{PAGE};stroke-width:4px;stroke-linejoin:round",
    "val": f"font-size:20px;font-weight:800;paint-order:stroke;stroke:{PAGE};stroke-width:4px;stroke-linejoin:round",
    "unit": "font-size:12px;font-weight:600;fill:#52514e",
    "f": "", "body": "stroke-linejoin:round",
}

def inline(m):
    tag = m.group(0)
    cm = re.search(r'\sclass="([^"]*)"', tag)
    if not cm:
        return tag
    st = ";".join(CLASS.get(c, "") for c in cm.group(1).split() if CLASS.get(c))
    tag = tag.replace(cm.group(0), "")
    if not st:
        return tag
    sm = re.search(r'\sstyle="([^"]*)"', tag)
    if sm:  # explicit style wins over class style
        return tag.replace(sm.group(0), f' style="{st};{sm.group(1)}"')
    return re.sub(r"^<(\w+)", rf'<\1 style="{st}"', tag)

svg = re.sub(r"<[a-zA-Z][^>]*>", inline, svg)
svg = re.sub(r"(\d+\.\d)\d+", r"\1", svg)                      # 1 decimal is plenty at this size
svg = svg.replace("#f6f5f1", PAGE)                              # map page background -> card background
svg = re.sub(r">(Canada|United States)<", lambda m: ">" + m.group(1).upper() + "<", svg)
svg = svg.replace('id="map"', 'id="region-map"').replace('width="100%"', "")
svg = svg.replace("<svg ", '<svg style="width: 100%; height: auto; display: block" ', 1)

R = json.loads((ROOT / "viz" / "region_caching_data.js").read_text(encoding="utf-8").split("=", 1)[1].rstrip().rstrip(";"))
na = {r["region"]: r for r in R["north_america"]}
tor, mon, slc = na["northamerica-northeast2"], na["northamerica-northeast1"], na["us-west3"]
near = min((r for r in na.values() if r["region"].startswith("us-")), key=lambda r: r["km_from_cmu"])
cache_kg = R["saved_kwh"]["plus10"] * R["central_g"] / 1000
f = lambda v: f"{v:.1f}" if v < 10 else f"{v:.0f}"
ratio = near["campus_kg_today"] / tor["campus_kg_today"]

def tile(color, big, text):
    return (f'<div style="background: #FFFFFF; border: 1px solid #E2E2DD; border-left: 6px solid {color}; border-radius: 5px; padding: 16px 18px; display: flex; flex-direction: column; gap: 4px">'
            f'<span style="font-family: \'Space Grotesk\', Inter, sans-serif; font-size: 30px; font-weight: 700; line-height: 1.1">{big} <span style="font-size: 14px; font-weight: 500; color: #4A4A4A">kg CO₂e / month</span></span>'
            f'<span style="font-size: 14px; color: #3F3F3F; line-height: 1.4">{text}</span></div>')

section = f"""{START}
<section aria-labelledby="where-title" style="display: flex; flex-direction: column; gap: 16px">
<div style="display: flex; flex-direction: column; gap: 4px">
<span style="font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: #4A4A4A">6 · Where to run it (P21)</span>
<h2 id="where-title" style="margin: 0; font-size: 22px; font-weight: 600">Same AI, same energy: run it in Toronto and CMU emits {ratio:.0f}× less CO₂e than in the nearest US data centers</h2>
<p style="margin: 0; font-size: 15px; line-height: 1.5; color: #3F3F3F; max-width: 900px">Each factory is a data-center region. Its chimney shows the CO₂e a month if <b>all</b> of CMU's AI ({R['kwh']['today']:.0f} kWh) ran there. Energy is the same everywhere; only the grid behind it changes.</p>
</div>
<div style="background: #FFFFFF; border: 1px solid #E2E2DD; border-radius: 5px; padding: 16px 20px; display: flex; flex-direction: column; gap: 10px">
{svg}
<div style="display: flex; flex-wrap: wrap; gap: 26px; align-items: center; font-size: 16px; font-weight: 600; color: #4A4A4A">
<span style="display: inline-flex; align-items: center; gap: 10px"><span style="color: #6D3FD9">cleaner grid</span><span style="display: inline-block; width: 340px; max-width: 60vw; height: 22px; border-radius: 5px; background: linear-gradient(90deg, #C4B5FD, #8B5CF6, #2A1268)"></span><span style="color: #2A1268">dirtier grid</span></span>
<span>Chimney height = kg CO₂e a month</span>
<span>★ CMU, Pittsburgh</span>
</div>
</div>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px">
{tile("#8B5CF6", f(near["campus_kg_today"]), f"Nearest US region ({near['label'].split(',')[0]}, {near['km_from_cmu']} km)")}
{tile("#C4B5FD", f(tor["campus_kg_today"]), f"Toronto, {tor['km_from_cmu']} km away: saves {f(near['campus_kg_today'] - tor['campus_kg_today'])} kg a month, about {round((near['campus_kg_today'] - tor['campus_kg_today']) / cache_kg)}× more than +10 pts of caching ({cache_kg:.1f} kg)")}
{tile("#2A1268", f(slc["campus_kg_today"]), f"Worst US choice (Salt Lake City): {round(slc['campus_kg_today'] / tor['campus_kg_today'])}× Toronto")}
</div>
<p style="margin: 0; font-size: 12px; line-height: 1.6; color: #4A4A4A">Energy is the same everywhere in our model ({R['kwh_range_today'][0]:.0f}–{R['kwh_range_today'][1]:.0f} kWh a month, estimate range); only the grid's carbon per kWh changes. Grid factors: Google Cloud region data listed in CodeCarbon <code>cloud/impact.csv</code> (13 Jul 2024), annual averages, so only Google Cloud regions appear. Factory positions are approximate city locations (some nudged, with a line to the true spot); distances are straight-line from CMU. The logs don't record where requests ran, so this is a what-if for choosing a hosting region. Toronto and Montréal are in Canada (data-residency rules may apply). Montréal: {mon['campus_kg_today']:.1f} kg. Numbers: <code>scripts/10_region_caching_co2.py</code>; map: us-atlas 3.0.1, world-atlas 2.0.2.</p>
</section>
{END}
"""

html = DASH.read_text(encoding="utf-8")
if START in html:  # replace an earlier embed
    html = re.sub(re.escape(START) + ".*?" + re.escape(END) + r"\n?", lambda m: section, html, flags=re.S)
else:
    html = html.replace("<!-- FOOTER -->", section + "\n<!-- FOOTER -->", 1)
html = html.replace('"$preview":{"width":1440,"height":3660}', '"$preview":{"width":1440,"height":4700}')
DASH.write_text(html, encoding="utf-8")
print("embedded map:", len(svg) // 1024, "KB of SVG")

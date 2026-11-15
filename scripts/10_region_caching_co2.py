"""Caching x grid region -> CO2e (diagram suggestion, P20).

CO2e saved by caching = energy saved by caching (kWh, our model) x grid carbon intensity (g/kWh).
Grid intensities: CodeCarbon cloud/impact.csv, pinned at commit ca104ad928 (2024-07-13), saved as
config/codecarbon_gcp_impact.csv. That file now lists only Google Cloud (GCP) regions: AWS and Azure
rows were removed in CodeCarbon commit 1a987a448e (2023-05-16). Values come from Google's
"Carbon free energy for Google Cloud regions" page (location-based grid intensity).

Energy is our ESTIMATE (central, scripts/06_carbon.py); data are SYNTHETIC (Oct 2026 logs).
The logs do not say where requests ran, so every region here is a what-if, not a measurement.

Output: viz/region_caching_data.js (window.REGION = {...}) and data-clean/region_caching_co2.csv
Run from repo root after 06 and 07: py scripts/10_region_caching_co2.py
"""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DC = ROOT / "data-clean"

grid = pd.read_csv(ROOT / "config" / "codecarbon_gcp_impact.csv", encoding="utf-8-sig")
grid = grid[["region", "country_name", "city", "impact"]].rename(columns={"impact": "g_per_kwh"})
grid["region"] = grid.region.replace({"me-cenrtal1": "me-central1"})  # typo in source file
grid = grid.sort_values("g_per_kwh").reset_index(drop=True)
cp = pd.read_csv(ROOT / "config" / "carbon_params.csv").set_index("param")["value"]
central_g = float(cp["grid_g_per_kwh_central"])  # 350, Jegham et al. (Azure/OpenAI), NOT CodeCarbon

calls = pd.read_csv(DC / "calls_costed_carbon__pricing_list.csv",
                    usecols=["is_success", "wh_central", "wh_nocache_central", "wh_low", "wh_high"])
ok = calls[calls.is_success]
kwh_now = calls.wh_central.sum() / 1000
kwh_nocache = calls.wh_nocache_central.sum() / 1000
scen = pd.read_csv(DC / "scenarios_by_tenant__pricing_list.csv")
camp = scen[scen.tenant_id == "ALL_CAMPUS"].set_index("scenario")

kwh = {  # campus, 30 days, central
    "no_caching": kwh_nocache,
    "today": kwh_now,
    "local_good_cache": float(camp.loc["L1_cache"].kwh_central),   # Dev + Sandbox reuse like the other teams
    "plus10_cache": float(camp.loc["G1_cache_step"].kwh_central),  # +10 points reuse, every team (per unit)
}
saved_kwh = {"today_vs_none": kwh_nocache - kwh_now,
             "local_good": kwh_now - kwh["local_good_cache"],
             "plus10": kwh_now - kwh["plus10_cache"]}
per_req = {"wh_cached_today": float(ok.wh_central.mean()), "wh_no_cache": float(ok.wh_nocache_central.mean())}

rows = []
for _, r in grid.iterrows():
    g = r.g_per_kwh
    rows.append({"region": r.region, "city": r.city, "country": r.country_name, "g_per_kwh": int(g),
                 "campus_kg_today": kwh_now * g / 1000,
                 "kg_saved_cache_today": saved_kwh["today_vs_none"] * g / 1000,
                 "kg_saved_local_good": saved_kwh["local_good"] * g / 1000,
                 "kg_saved_plus10": saved_kwh["plus10"] * g / 1000,
                 "g_per_req_cached": per_req["wh_cached_today"] * g / 1000,
                 "g_per_req_nocache": per_req["wh_no_cache"] * g / 1000})
out = pd.DataFrame(rows)
out.to_csv(DC / "region_caching_co2.csv", index=False)

# North American map layer (P21): region coordinates + great-circle distance from CMU
import math
xy = pd.read_csv(ROOT / "config" / "region_coords.csv").set_index("region")
cmu = xy.loc["CMU"]
def km(a, b):
    p1, p2, dl = map(math.radians, [a.lat, b.lat, b.lon - a.lon])
    return 6371 * math.acos(min(1, math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl)))
kwh_lo, kwh_hi = calls.wh_low.sum() / 1000, calls.wh_high.sum() / 1000
na = []
for r in rows:
    if r["region"] not in xy.index: continue
    c = xy.loc[r["region"]]
    na.append({**r, "lat": float(c.lat), "lon": float(c.lon), "label": c.label, "km_from_cmu": round(km(cmu, c)),
               "campus_kg_low_energy": kwh_lo * r["g_per_kwh"] / 1000, "campus_kg_high_energy": kwh_hi * r["g_per_kwh"] / 1000,
               "kg_by_caching": {k: v * r["g_per_kwh"] / 1000 for k, v in kwh.items()}})
pd.DataFrame(na).drop(columns="kg_by_caching").to_csv(DC / "region_map_north_america.csv", index=False)

payload = {"regions": rows, "north_america": na, "cmu": {"lat": float(cmu.lat), "lon": float(cmu.lon)},
           "requests": int(len(calls)), "success": int(calls.is_success.sum()), "kwh": kwh, "saved_kwh": saved_kwh, "per_req": per_req,
           "central_g": central_g, "kwh_range_today": [float(calls.wh_low.sum() / 1000), float(calls.wh_high.sum() / 1000)],
           "plus10_usd": float(-camp.loc["G1_cache_step"].delta_cost_usd),
           "local_good_usd": float(-camp.loc["L1_cache"].delta_cost_usd),
           "source": "CodeCarbon cloud/impact.csv @ca104ad928 (2024-07-13), GCP only; values from Google Cloud region carbon data"}
(ROOT / "viz").mkdir(exist_ok=True)
(ROOT / "viz" / "region_caching_data.js").write_text("window.REGION = " + json.dumps(payload, indent=1) + ";\n", encoding="utf-8")

for r in sorted(na, key=lambda r: r["g_per_kwh"]):
    print(f"{r['label']:22} {r['g_per_kwh']:4} g  {r['campus_kg_today']:6.1f} kg/mo  {r['km_from_cmu']:5} km")
print(f"campus kWh now {kwh_now:.1f}, no cache {kwh_nocache:.1f}; saved today {saved_kwh['today_vs_none']:.2f}, "
      f"local good {saved_kwh['local_good']:.2f}, +10pt {saved_kwh['plus10']:.2f} kWh")
print("per request Wh", per_req)
for g in [grid.g_per_kwh.min(), 94, central_g, 588, grid.g_per_kwh.max()]:
    print(f"{g:>5} g/kWh: campus {kwh_now*g/1000:7.1f} kg | cache today saves {saved_kwh['today_vs_none']*g/1000:5.2f} | +10pt saves {saved_kwh['plus10']*g/1000:5.2f}")

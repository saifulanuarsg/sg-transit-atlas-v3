#!/usr/bin/env python3
"""SG Transit Atlas v3 — Ship 1.1 bake (composable audience builder).

Ships RAW subzone counts so the client composes any audience live:
age bands (19, x sex), dwelling groups (income proxy), PA context rates
(movers, daytime). Route scoring happens client-side.

Reads the v2 atlas data read-only; never modifies it.

Outputs:
  data/subzones.json  geojson: sz, pa, pop, am[19], af[19], dw[7], mix, mv, dt
  data/stops_v3.json  {code: [allocated_weekday_boardings, subzone_feature_index]}
  data/routes.json    {svc: {name, segs, stops[], raw_wd}}
  data/meta.json      band labels, national counts/rates, cap, floor, sources, assumptions
"""
import json, os, pickle
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.join(HERE, "..", "2026-07-14-sg-bus-routes-map", "data")
TEST = os.path.join(HERE, "..", "2026-07-18-v3-discrimination-test", "data")
OUT = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)

CAP = 300.0
INDEX_MODE_VOLUME_FLOOR = 5000

BANDS = ["0_4","5_9","10_14","15_19","20_24","25_29","30_34","35_39","40_44","45_49",
         "50_54","55_59","60_64","65_69","70_74","75_79","80_84","85_89","90andOver"]
BAND_LABELS = ["0–4","5–9","10–14","15–19","20–24","25–29","30–34","35–39","40–44","45–49",
               "50–54","55–59","60–64","65–69","70–74","75–79","80–84","85–89","90+"]
DW_FIELDS = ["HDBDwellings_1_and2_RoomFlats1","HDBDwellings_3_RoomFlats","HDBDwellings_4_RoomFlats",
             "HDBDwellings_5_RoomandExecutiveFlats","CondominiumsandOtherApartments",
             "LandedProperties","Others"]
DW_LABELS = ["HDB 1–2R","HDB 3R","HDB 4R","HDB 5R/Exec","Condo/Apt","Landed","Others"]

def num(x):
    try: return float(str(x).replace(",", ""))
    except (ValueError, TypeError): return 0.0

raw = pickle.load(open(os.path.join(TEST, "census_raw.pkl"), "rb"))
eth_rows = pickle.load(open(os.path.join(TEST, "ethnic_raw.pkl"), "rb"))

def walk(rows):
    pa = None
    for r in rows:
        nm = r["Number"].strip()
        if nm == "Total": yield ("__NATIONAL__", "__NATIONAL__", r); continue
        if nm.endswith(" - Total"):
            pa = nm[:-8].strip().upper(); yield ("__PA__", pa, r); continue
        yield (pa, nm.upper(), r)

sz, pa_pop, nat = {}, {}, {}
for pa, nm, r in walk(raw["age"]):
    tot = num(r["Total_Total"])
    if tot <= 0: continue
    am = [int(num(r.get(f"Males_{b}"))) for b in BANDS]
    af = [int(num(r.get(f"Females_{b}"))) for b in BANDS]
    if pa == "__NATIONAL__": nat.update({"pop": int(tot), "am": am, "af": af})
    elif pa == "__PA__": pa_pop[nm] = tot
    else: sz.setdefault((pa, nm), {}).update({"pop": int(tot), "am": am, "af": af})
for pa, nm, r in walk(raw["dw"]):
    tot = num(r["Total"])
    if tot <= 0: continue
    dw = [int(num(r.get(f))) for f in DW_FIELDS]
    if pa == "__NATIONAL__": nat["dw"] = dw
    elif pa != "__PA__": sz.setdefault((pa, nm), {})["dw"] = dw
for pa, nm, r in walk(eth_rows):
    tot = num(r["Total_Total"])
    if tot <= 0: continue
    mix = {"chinese": round(num(r.get("Chinese_Total")) / tot, 3),
           "malay": round(num(r.get("Malays_Total")) / tot, 3),
           "indian": round(num(r.get("Indians_Total")) / tot, 3),
           "others": round(num(r.get("Others_Total")) / tot, 3)}
    if pa == "__NATIONAL__": nat["mix"] = mix
    elif pa != "__PA__": sz.setdefault((pa, nm), {})["mix"] = mix
print(f"census: {len(sz)} populated subzones | national pop {nat['pop']:,}")

pas = json.load(open(os.path.join(V2, "planning_areas.geojson")))
pa_mv, pa_dt = {}, {}
tot_mv = tot_dt = 0
for f in pas["features"]:
    p = f["properties"]; nm = p["name"].upper()
    if p.get("mover_vol"):
        tot_mv += p["mover_vol"]
        if pa_pop.get(nm): pa_mv[nm] = p["mover_vol"] / pa_pop[nm]
    if p.get("daytime_pop"):
        tot_dt += p["daytime_pop"]
        if pa_pop.get(nm): pa_dt[nm] = p["daytime_pop"] / pa_pop[nm]
nat_mv = tot_mv / nat["pop"]; nat_dt = tot_dt / nat["pop"]

# ---- stop -> subzone ---------------------------------------------------------
szgj = json.load(open(os.path.join(TEST, "subzones.geojson")))
polys = []
for f in szgj["features"]:
    p, g = f["properties"], f["geometry"]
    coords = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    rings = [ring for poly in coords for ring in poly]
    xs = [pt[0] for ring in rings for pt in ring]; ys = [pt[1] for ring in rings for pt in ring]
    polys.append(((min(xs), min(ys), max(xs), max(ys)), rings, p["SUBZONE_N"], p["PLN_AREA_N"]))

def crossings(x, y, ring):
    n, c, j = len(ring), 0, len(ring) - 1
    for i in range(n):
        xi, yi, xj, yj = ring[i][0], ring[i][1], ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi: c += 1
        j = i
    return c

def locate(x, y):
    for i, (bb, rings, s, pa) in enumerate(polys):
        if bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]:
            if sum(crossings(x, y, r) for r in rings) % 2: return i
    return -1

stops = json.load(open(os.path.join(V2, "stops.json")))
stop_szi = {c: locate(lng, lat) for c, (lng, lat, *_ ) in stops.items()}
print(f"stops located: {sum(1 for v in stop_szi.values() if v >= 0)}/{len(stops)}")

# ---- consumer-behaviour POI layers (stop-catchment density, 400 m) ----------
# Locations are observed (cited registries); the behaviour itself is inferred.
RAW = os.path.join(HERE, "rawdata")

def load_poi(fn):
    return [(p["lng"], p["lat"]) for p in json.load(open(os.path.join(V2, fn)))]

def load_new_geojson(path, name_from=None):
    gj = json.load(open(path))
    return [(f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1])
            for f in gj["features"] if f.get("geometry", {}).get("type") == "Point"]

hawker = load_new_geojson(os.path.join(RAW, "hawker_centres.geojson"))
preschools = load_new_geojson(os.path.join(RAW, "preschools.geojson"))
json.dump([{"lng": x, "lat": y} for x, y in hawker], open(os.path.join(OUT, "poi_hawker.json"), "w"))
json.dump([{"lng": x, "lat": y} for x, y in preschools], open(os.path.join(OUT, "poi_preschools.json"), "w"))

BEHAVIOURS = [
    ("grocery",   "Grocery shoppers",        "supermarkets (OSM, chain-verified)",        load_poi("poi_supermarkets.json")),
    ("mall",      "Mall shoppers",           "shopping malls (OSM)",                      load_poi("poi_malls.json")),
    ("fnb",       "F&B — chain dining",      "HPB healthier-dining outlets",              load_poi("poi_fnb.json")),
    ("hawkerf",   "F&B — hawker",            "NEA hawker centres (d_4a086da0…)",          hawker),
    ("yfam",      "Young families",          "ECDA pre-school locations (d_61eefab9…)",   preschools),
    ("sfam",      "School-age families",     "MOE schools + MSF student care",            load_poi("poi_schools.json") + load_poi("poi_studentcare.json")),
    ("fit",       "Fitness & sports",        "SportSG facilities",                        load_poi("poi_sport.json")),
    ("health",    "Health & pharmacy",       "HSA registered pharmacies",                 load_poi("poi_pharmacies.json")),
    ("eldercare", "Seniors' services",       "AIC eldercare services",                    load_poi("poi_eldercare.json")),
    ("remit",     "Migrant remitters",       "MAS remittance shopfronts",                 load_poi("poi_remittance.json")),
    ("tourist",   "Tourists",                "STB hotels + attractions",                  load_poi("poi_hotels.json") + load_poi("poi_tourism.json")),
    ("community", "Community heartland",     "PA community clubs + NLB libraries",        load_poi("poi_cc.json") + load_poi("poi_libraries.json")),
]
import math
R400 = 400.0
def count_within(stop_lng, stop_lat, pts):
    dlat = R400 / 110540.0
    dlng = R400 / (111320.0 * math.cos(math.radians(stop_lat)))
    c = 0
    for x, y in pts:
        if abs(x - stop_lng) > dlng or abs(y - stop_lat) > dlat: continue
        dx = (x - stop_lng) * 111320.0 * math.cos(math.radians(stop_lat))
        dy = (y - stop_lat) * 110540.0
        if dx * dx + dy * dy <= R400 * R400: c += 1
    return c

# ---- spend propensity (HES 2023 by dwelling) + digital propensity (IMDA) ----
# Ecological joins: national rates joined through each subzone's housing / age
# mix. Assumes rates are uniform within a dwelling type / age band.
HES_DIVS = [  # (division rowNo, chip label)
    ("11", "Eating out"), ("1", "Groceries"), ("3", "Clothing & footwear"),
    ("5", "Home & furnishings"), ("6", "Health spend"), ("7", "Transport spend"),
    ("8", "Info & communication"), ("9", "Recreation & culture"), ("10", "Education spend"),
    ("13", "Insurance & financial"), ("14", "Personal care & misc")]
# persona-grade detail rows (summed) — appended to the same spend-lever system
HES_DETAIL = [
    (["9.8", "7.4", "12"], "Travel"),                 # package holidays + air fares + accommodation
    (["14.1.1", "14.2.1"], "Beauty & grooming"),      # hairdressing/grooming + jewellery & watches
    (["7.1", "7.2"], "Car ownership"),                # vehicle purchase + running costs
    (["9.2.1.1", "9.4.3.1"], "Video gaming"),         # video games + subscriptions (small base)
    (["9.3.2", "9.4.5"], "Pet owners"),               # pet products + vet services
    (["9.6"], "Entertainment & culture"),             # cinema/theatre/concert + cultural services
    (["8.1"], "Tech equipment"),                      # info & comm equipment
    (["10.2"], "Tuition & enrichment"),               # private tuition + courses
]
# HES dwelling columns in census dw[] order 0..5 (Others dw[6] excluded, shares renormalised)
HES_COL_ORDER = ["HDB Dwellings|1- & 2-Room Flats 2/", "HDB Dwellings|3-Room Flats",
                 "HDB Dwellings|4-Room Flats", "HDB Dwellings|5-Room & Executive Flats",
                 "Condominiums & Other Apartments", "Landed Properties"]

def flatcols(cols, pre=""):
    out = {}
    for c in cols:
        if "columns" in c: out.update(flatcols(c["columns"], pre + c["key"] + "|"))
        else: out[pre + c["key"]] = c["value"]
    return out

hes_rows = {str(r["rowNo"]): r for r in json.load(open(os.path.join(RAW, "hes2023_by_dwelling.json")))}
hes_spend = []  # per lever: [spend by 6 dwelling types]
for div, _ in HES_DIVS:
    fc = flatcols(hes_rows[div]["columns"])
    hes_spend.append([num(fc.get(k)) for k in HES_COL_ORDER])
for rows_, _ in HES_DETAIL:
    vec = [0.0] * 6
    for rn in rows_:
        fc = flatcols(hes_rows[rn]["columns"])
        vec = [a + num(fc.get(k)) for a, k in zip(vec, HES_COL_ORDER)]
    hes_spend.append(vec)
SPEND_LABELS = [lb for _, lb in HES_DIVS] + [lb for _, lb in HES_DETAIL]

def dw_shares6(dw):
    tot = sum(dw[:6])
    return [x / tot for x in dw[:6]] if tot > 0 else None

nat_sh6 = dw_shares6(nat["dw"])
nat_spend = [sum(s * v for s, v in zip(nat_sh6, spend)) for spend in hes_spend]

# IMDA online shoppers by age (latest survey year in the dataset — 2018; the
# age GRADIENT is the usable signal, absolute levels are outdated)
imda = json.load(open(os.path.join(RAW, "imda_online_shoppers.json")))
latest_yr = max(r["year"] for r in imda)
imda_rates = {r["age_group"]: num(r["percentage"]) / 100 for r in imda if r["year"] == latest_yr}
IMDA_BANDS = {"15 to 24 years": [3, 4], "25 to 34 years": [5, 6], "35 to 49 years": [7, 8, 9],
              "50 to 59 years": [10, 11], "60 and above": list(range(12, 19))}

def online_rate(am, af):
    num_ = den = 0.0
    for grp, bl in IMDA_BANDS.items():
        p = sum(am[b] + af[b] for b in bl)
        num_ += p * imda_rates.get(grp, 0); den += p
    return num_ / den if den > 0 else None

nat_online = online_rate(nat["am"], nat["af"])

# IMDA internet usage by age — 2024 vintage, three broad bands (current gradient)
dg_recs = json.load(open(os.path.join(RAW, "internet_by_age_annual.json")))
dg_rates = {}
for r in dg_recs:
    s = r["DataSeries"]
    if "18 - 39" in s: dg_rates["young"] = num(r["2024"]) / 100
    elif "40 - 59" in s: dg_rates["mid"] = num(r["2024"]) / 100
    elif "60 And Over" in s: dg_rates["senior"] = num(r["2024"]) / 100
DG_BANDS = {"young": [4, 5, 6, 7], "mid": [8, 9, 10, 11], "senior": list(range(12, 19))}
# (survey band 18-39 mapped to census 20-39; the 18-19 sliver is approximated — stated)

def digital_rate(am, af):
    n = d = 0.0
    for grp, bl in DG_BANDS.items():
        p = sum(am[b] + af[b] for b in bl)
        n += p * dg_rates[grp]; d += p
    return n / d if d > 0 else None

nat_digital = digital_rate(nat["am"], nat["af"])

def propensity(m):
    """per-subzone: sp[] spend indices + op online index (vs national = 100)"""
    out = {}
    sh = dw_shares6(m["dw"]) if m.get("dw") else None
    if sh:
        out["sp"] = [round(sum(s * v for s, v in zip(sh, spend)) / nspend * 100, 1)
                     for spend, nspend in zip(hes_spend, nat_spend)]
    if m.get("am"):
        r = online_rate(m["am"], m["af"])
        if r is not None: out["op"] = round(r / nat_online * 100, 1)
        r2 = digital_rate(m["am"], m["af"])
        if r2 is not None: out["dg"] = round(r2 / nat_digital * 100, 1)
    return out

print(f"HES 2023 divisions baked: {len(HES_DIVS)} | national eating-out ${nat_spend[0]:.0f}/mo | "
      f"IMDA online-shopper vintage {latest_yr}, national rate {nat_online:.1%}")

# ---- allocation + outputs ----------------------------------------------------
route_stops = json.load(open(os.path.join(V2, "route_stops.json")))
vol = json.load(open(os.path.join(V2, "stop_volume.json")))
svc_per_stop = defaultdict(int)
for svc, dirs in route_stops.items():
    for c in {c for d in dirs for c in d}: svc_per_stop[c] += 1

stops_out = {}
for c, (lng, lat, *_ ) in stops.items():
    w = (vol.get(c) or {}).get("wd", 0)
    if w <= 0 and stop_szi[c] < 0: continue
    beh = [count_within(lng, lat, pts) for _, _, _, pts in BEHAVIOURS]
    stops_out[c] = [round(w / max(svc_per_stop.get(c, 1), 1), 1), stop_szi[c], beh]

# volume-weighted network baseline density per behaviour layer
b_base = []
for bi in range(len(BEHAVIOURS)):
    num = sum(v[0] * v[2][bi] for v in stops_out.values())
    den = sum(v[0] for v in stops_out.values())
    b_base.append(round(num / den, 4))
print("behaviour baselines:", {BEHAVIOURS[i][0]: b_base[i] for i in range(len(BEHAVIOURS))})

net = json.load(open(os.path.join(V2, "network.json")))
routes_out = {}
for s in net["services"]:
    if s["feeder"]: continue
    n = s["n"]
    dirs = route_stops.get(n, [])
    codes = sorted({c for d in dirs for c in d})
    raw_wd = sum((vol.get(c) or {}).get("wd", 0) for c in codes)
    routes_out[n] = {"name": s["name"], "raw_wd": round(raw_wd), "stops": codes,
                     "segs": [[[round(x, 5), round(y, 5)] for x, y in seg] for seg in s["segs"]]}
print(f"trunk routes: {len(routes_out)}")

feats = []
for f in szgj["features"]:
    p, g = f["properties"], f["geometry"]
    m = sz.get((p["PLN_AREA_N"], p["SUBZONE_N"]), {})
    props = {"sz": p["SUBZONE_N"].title(), "pa": p["PLN_AREA_N"].title()}
    if m.get("pop"):
        props.update({"pop": m["pop"], "am": m["am"], "af": m["af"]})
        if "dw" in m: props["dw"] = m["dw"]
        if "mix" in m: props["mix"] = m["mix"]
        props.update(propensity(m))
    if p["PLN_AREA_N"] in pa_mv: props["mv"] = round(pa_mv[p["PLN_AREA_N"]], 5)
    if p["PLN_AREA_N"] in pa_dt: props["dt"] = round(pa_dt[p["PLN_AREA_N"]], 4)
    def rnd(coords, d=0):
        return [rnd(c, d + 1) for c in coords] if isinstance(coords[0], list) else [round(coords[0], 5), round(coords[1], 5)]
    feats.append({"type": "Feature", "properties": props,
                  "geometry": {"type": g["type"], "coordinates": rnd(g["coordinates"])}})

meta = {
    "built": "2026-07-18", "cap": CAP, "index_mode_floor": INDEX_MODE_VOLUME_FLOOR,
    "bands": BAND_LABELS, "dw_labels": DW_LABELS,
    "behaviours": [{"k": k, "label": lb, "source": src, "n": len(pts)} for k, lb, src, pts in BEHAVIOURS],
    "behaviour_base": b_base, "behaviour_floor": 25.0,
    "spend_labels": SPEND_LABELS, "imda_vintage": latest_yr, "digital_vintage": 2024,
    "national": {"pop": nat["pop"], "am": nat["am"], "af": nat["af"], "dw": nat["dw"],
                 "mv_rate": round(nat_mv, 5), "dt_rate": round(nat_dt, 4), "mix": nat["mix"]},
    "sources": {
        "volume": "LTA DataMall passenger volume by bus stop — weekday daily tap-ins (v2 bake, Jul 2026). Hourly dayparts pending DataMall account key.",
        "subzone": "URA Master Plan 2019 subzone boundaries (data.gov.sg d_8594ae9ff96d0c708bc2af633048edfb)",
        "census": "SingStat Census of Population 2020: age x sex (d_d95ae740c0f8961a0b10435836660ce0), dwelling (d_7f243956483d5901f237e6f87b096636), ethnic group (d_e7ae90176a68945837ad67892b898466)",
        "movers": "HDB resale txns 12mo to 2026-07 (d_8b84c4ee58e3cfc0ece0d773c8ca6abc), planning-area level",
        "daytime": "Census 2020 employed residents by workplace planning area (d_be89529e906103da82ff06adec019f17)",
        "behaviour": "Consumer-behaviour layers: POI registries (OneMap themes, OSM, NEA hawker centres d_4a086da0a5553be1d89383cd90d07ecd, ECDA pre-schools d_61eefab99958fd70e6aab17320a71f1c) counted within 400 m of each stop. Locations observed; the behaviour is inferred.",
        "spend": "Spend propensity: HES 2023, average monthly household expenditure by type of goods and services (detailed) x dwelling type (SingStat Tablebuilder table 17971), joined through each subzone's housing mix (Others dwellings excluded, shares renormalised).",
        "digital": f"Digital propensity: IMDA online shoppers by age (d_276031cfd1b2929bb795cdcedd54989e, latest machine-readable year {latest_yr} — gradient signal) and individuals' internet usage by age group, 2024 (d_3f4bfee2d42f8fb3bea3218c01aa9902, three broad bands; survey band 18-39 approximated onto census 20-39), each joined through subzone age mix.",
        "personas": "Persona presets are one-click recipes over the open-data levers, named after MooveSMART's taxonomy for comparability. Each shows its ingredients in the audience line. Job Seekers is deliberately not scored: no open-data signal exists (MOM unemployment is national-only)."},
    "assumptions": [
        "Equal-share allocation: a stop's tap-ins are split equally across all services calling there (frequency data not held; OD-constrained allocation planned).",
        "Residence join: boarders are profiled as residents of the stop's subzone. This is the model's weakest link.",
        "No ride-length factor yet: the unit is target-audience boardings per weekday, not impressions.",
        "Indices capped at 300 (x3 national); capped contribution is tracked and widens the confidence label.",
        "Combined levers multiply as independent shares (geometric mean of indices); real levers correlate, so combined indices overstate concentration — treat multi-lever audiences as directional.",
        "Behaviour levers are stop-catchment POI density indices: being near a supermarket is evidence of grocery-shopper presence, not proof of shopping. Density uses an additive-smoothed ratio ((count+1)/(baseline+1)), floored at 25 and capped at 300; behaviour levers always carry at most 'low' confidence.",
        "Spend and digital propensity are ecological joins: national rates by dwelling type (HES 2023) or age band (IMDA) applied to each subzone's mix. They assume rates are uniform within a type/band, so they cannot be combined with the Housing or Age levers they derive from — the UI enforces this."]}

json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(OUT, "subzones.json"), "w"), separators=(",", ":"))
json.dump(stops_out, open(os.path.join(OUT, "stops_v3.json"), "w"), separators=(",", ":"))
json.dump(routes_out, open(os.path.join(OUT, "routes.json"), "w"), separators=(",", ":"))
json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), separators=(",", ":"))
old = os.path.join(OUT, "scores.json")
if os.path.exists(old): os.remove(old)
for fn in ("subzones.json", "stops_v3.json", "routes.json", "meta.json"):
    print(fn, round(os.path.getsize(os.path.join(OUT, fn)) / 1e6, 2), "MB")

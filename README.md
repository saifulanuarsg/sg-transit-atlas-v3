# SG Transit Atlas v3 — audience planner (Ship 1)

Standalone app. **Separate from the v2 atlas by design** — the v2 repo
(`_outputs/2026-07-14-sg-bus-routes-map/`) is read at build time and never modified.
When deployed, v3 gets its own link, not a path inside the v2 deployment.

Built 18 Jul 2026 against `_outputs/2026-07-18-transit-atlas-v3-audience-module-spec/spec.md`
(Ship 1 scope) and the design lessons from `_outputs/2026-07-18-v3-discrimination-test/VERDICT.md`
(index cap ×3 national, volume floor in index mode, empty-subzone handling).

## What it does

Compose any audience with toggles → 293 trunk bus routes ranked live by the
internal (passenger) model. Levers: age (19 five-year bands with presets — all
ages, adults 20+, 20–34, 25–54, 25–44, children 0–9, 65+, or custom band picks),
sex (any/female/male), housing as the income proxy (HDB 1–3R, HDB 4–5R/Exec,
private), and two planning-area context layers (new movers, daytime workforce)
that widen the confidence label when active. Scoring is client-side from raw
subzone census counts; combined levers join by geometric mean and are flagged
"directional" because correlated levers overstate concentration.

Subzone choropleth of the composed index; route detail card with figures grouped
in three always-separate layers (Measured / Modelled / Judgement); language mix
shown as creative guidance only — deliberately not a targeting filter. Rank by
target boardings (default) or audience index (volume floor 5,000 applied). With
no levers selected the ranking is pure measured volume ("everyone"). No blended
score exists anywhere.

## Run

`preview_start atlas-v3` (launch.json) or:
`python3 -m http.server 8763 --directory _outputs/2026-07-18-transit-atlas-v3`

## Rebuild

`python3 build_v3.py` — reads v2 `data/` (stops, route_stops, stop_volume, network,
planning_areas) plus the discrimination-test downloads (subzone boundaries, census
pickles), writes `data/{subzones,routes,scores}.json` (~1.9 MB total).

## Ship 1 stated gaps (also in the in-app method note)

- Hourly dayparts pending a DataMall account key (volumes are weekday daily).
- Equal-share stop-to-route allocation (frequency data not held; OD is Ship 3).
- Unit is target-audience boardings per weekday, not impressions (no ride-length
  factor yet).
- External (street-level) model is Ship 2.

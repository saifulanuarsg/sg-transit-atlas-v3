# SG Media Planner (formerly Transit Atlas v3)

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

**Consumer behaviour (Ship 1.2):** twelve location-inferred behaviour levers,
each a stop-catchment density index (places within 400 m of a stop, indexed to
the volume-weighted network average, floored 25 / capped 300): grocery shoppers
(supermarkets), mall shoppers, F&B chain dining (HPB), F&B hawker (NEA hawker
centres, new fetch), young families (ECDA pre-schools, new fetch, 2,290 pts),
school-age families, fitness, health & pharmacy, seniors' services, migrant
remitters, tourists, community heartland. Locations are observed from cited
registries; the behaviour is inferred and always carries at most "low"
confidence. Behaviour levers score at stop level and combine with demographic
levers by geometric mean. HES 2023 spend-by-dwelling propensity was sought and
identified but its by-dwelling tables are not machine-readable on data.gov.sg
yet — named as the next data source, not proxied.

**Spend & digital propensity (Ship 1.3):** eleven spend levers from HES 2023 —
average monthly household expenditure by goods/services division × dwelling type
(SingStat Tablebuilder table 17971, fetched via the Tablebuilder API), joined
through each subzone's housing mix: eating out, groceries, clothing, home &
furnishings, health, transport, info & communication, recreation & culture,
education, insurance & financial, personal care. Plus an online-shoppers lever
from IMDA's infocomm usage survey (online shoppers by age,
d_276031cfd1b2929bb795cdcedd54989e; latest machine-readable year 2018 — the age
gradient is the signal, levels are outdated), joined through age mix. Both are
ecological joins and the UI enforces the collinearity gate: a propensity chip
clears the Housing/Age lever it derives from, and vice versa. Raw source tables
are vendored in rawdata/ so rebuilds don't depend on live endpoints.

**Persona presets (Ship 1.4):** a one-click row mirroring MooveSMART's 16-persona
taxonomy, each a transparent recipe over the levers (hover shows ingredients).
Backed by 8 new persona-grade spend levers from HES 2023 detail rows (travel =
package holidays + air fares + accommodation; beauty & grooming; car ownership =
vehicle purchase + running costs; video gaming; pet owners; entertainment &
culture; tech equipment; tuition & enrichment — 19 spend levers total) and a
2024-vintage "Digitally active" lever (IMDA internet usage by age,
d_3f4bfee2d42f8fb3bea3218c01aa9902). Honest divergences: Property Owner →
Property Intender (movers is what data supports); Car Owner is flagged for
external formats; Gaming is flagged as a small spend base; **Job Seekers is a
disabled chip** — no open-data signal exists and scoring it would be assertion.

Sought and ruled out this round: NLB loans by branch (only a national annual
index exists — no per-branch data), EMA electricity by planning area (real but
collinear with the dwelling lever), NEA licensed eating establishments (exists,
needs postal-code geocoding — future upgrade for the F&B layer).

Subzone choropleth of the composed index; route detail card with figures grouped
in three always-separate layers (Measured / Modelled / Judgement); language mix
shown as creative guidance only — deliberately not a targeting filter. Rank by
target boardings (default) or audience index (volume floor 5,000 applied). With
no levers selected the ranking is pure measured volume ("everyone"). No blended
score exists anywhere.

## Run

`preview_start media-planner` (launch.json) or:
`python3 -m http.server 8763 --directory _outputs/2026-07-18-transit-atlas-v3`

## Rebuild

`python3 build_v3.py` — reads v2 `data/` (stops, route_stops, stop_volume, network,
planning_areas) plus the discrimination-test downloads (subzone boundaries, census
pickles), writes `data/{subzones,routes,scores}.json` (~1.9 MB total).

## Ship 2 (19 Jul 2026): external model + client export

Two models, one asset, never summed. The **external (street-level) model** scores
bus exteriors: each route corridor is resampled every ~100 m and composed from
corridor tap-ins (all stops ≤150 m, any service — waiting people see exteriors),
street-activity places ≤150 m, and the crossed subzones carrying the composed
audience. Output is a relative index (100 = network average) — no pedestrian-count
dataset exists in open data, so it is a ranking signal, never a people count, at
most "low" confidence, ranked by exposure-km (density accumulated over route
length). Vehicular exposure is a stated under-read (no open link-level traffic
counts). Monsoon visibility is an advisory, deliberately not applied to figures.

**Client summary** (⎙ button): print-ready one-pager — audience definition, top-10
routes with internal and external figures side by side, the how-to-read note
("modelled opportunities to see — not panel-measured"), ethnicity policy line,
sources and vintages.

## Stated gaps (also in the in-app method note)

- Hourly dayparts pending a DataMall account key (volumes are weekday daily).
- Equal-share stop-to-route allocation (frequency data not held; OD is Ship 3).
- Internal unit is target-audience boardings per weekday, not impressions (no
  ride-length factor yet).
- External model has no ground truth — calibration counts are a budget decision.

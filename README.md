# Boating Days – web version

Free boating forecast for Kleinmond, Pringle Bay (Maasbaai), Gordon's Bay and Hermanus.
Part of **Kleinmond App Studio** – https://www.facebook.com/KleinmondAppStudio

Live page: https://kleinmondappstudio.github.io/boating-days/

## How it works

```
GitHub (every 3 hours)                 Everyone
┌──────────────────────────┐          ┌────────────────────────┐
│ scripts/fetch_forecast.py│          │ Web page (index.html)  │
│  • Open-Meteo weather    │  writes  │ Phone app (later)      │
│  • Open-Meteo waves      │ ───────► │  both read ONE file:   │
│  • Stormglass tides      │          │  data/forecast.json    │
│    (once a day only)     │          └────────────────────────┘
└──────────────────────────┘
```

* The weather services are asked **4 times per run (one per spot), whatever the number of users**.
* Stormglass (10 free calls a day) is asked **once a day** = 4 calls.
* Each person's limits are worked out **in their own browser** and saved on their own device.

## Files

| File | What it does |
|---|---|
| `index.html` | The web page |
| `assets/` | Logo, cover banner, icons (same as the Facebook Page) |
| `data/forecast.json` | The forecast, written by the script |
| `scripts/fetch_forecast.py` | Collects the forecast. Standard Python only |
| `.github/workflows/update-forecast.yml` | The 3-hour timer |

## Settings

* **Pages**: Settings → Pages → Deploy from a branch → `main` / root.
* **Tides (optional)**: Settings → Secrets and variables → Actions → secret `STORMGLASS_KEY`. Never put the key in a file.
* **Run now**: Actions → Update forecast → Run workflow.

The future Play Store app can read the same file:
`https://kleinmondappstudio.github.io/boating-days/data/forecast.json`

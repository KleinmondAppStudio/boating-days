#!/usr/bin/env python3
"""
Boating Days - forecast collector (runs on GitHub every 3 hours).

Fetches the forecast ONCE for every launch spot and saves it to
data/forecast.json. The web page and the phone app read that one file,
so the weather services are asked 4 times per run, no matter how many
people use Boating Days.

Sources
  * Open-Meteo weather + marine: free, no key, every run.
  * Stormglass tides: 10 free calls a day, so it is asked only once a day
    (4 spots = 4 calls). Needs the STORMGLASS_KEY secret on GitHub.
    Without the secret, tides are simply left out.

Only the Python standard library is used, so nothing needs installing.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

TZ_NAME = "Africa/Johannesburg"
SAST = timezone(timedelta(hours=2))
DAYS = 7

SPOTS = [
    {"id": "kleinmond", "name": "Kleinmond Harbour", "lat": -34.3437, "lng": 19.0225},
    {"id": "maasbaai", "name": "Maasbaai Slipway (Pringle Bay)", "lat": -34.3465, "lng": 18.8290},
    {"id": "gordonsbay", "name": "Gordon's Bay Harbour", "lat": -34.1610, "lng": 18.8660},
    {"id": "hermanus", "name": "Hermanus New Harbour", "lat": -34.4215, "lng": 19.2370},
]

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "forecast.json")


def get_json(url, headers=None, timeout=25, attempts=3):
    """Fetch JSON, trying up to 3 times with a pause, and say clearly what went wrong."""
    last = None
    for n in range(1, attempts + 1):
        req = urllib.request.Request(url, headers={"User-Agent": "KleinmondAppStudio-BoatingDays/1.0", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            last = f"HTTP {e.code}: {body}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        print(f"  attempt {n} failed for {url.split('?')[0]} -> {last}", file=sys.stderr)
        time.sleep(5 * n)
    raise RuntimeError(last)


def weather(spot):
    q = urllib.parse.urlencode({
        "latitude": spot["lat"],
        "longitude": spot["lng"],
        "hourly": "temperature_2m,wind_speed_10m,wind_gusts_10m,wind_direction_10m,"
                  "precipitation_probability,visibility",
        "daily": "sunrise,sunset",
        "wind_speed_unit": "kmh",
        "timezone": TZ_NAME,
        "forecast_days": DAYS,
    })
    return get_json("https://api.open-meteo.com/v1/forecast?" + q)


def marine(spot):
    q = urllib.parse.urlencode({
        "latitude": spot["lat"],
        "longitude": spot["lng"],
        "hourly": "wave_height,swell_wave_height,swell_wave_period",
        "timezone": TZ_NAME,
        "forecast_days": DAYS,
    })
    return get_json("https://marine-api.open-meteo.com/v1/marine?" + q)


def tides(spot, key):
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=DAYS)
    q = urllib.parse.urlencode({
        "lat": spot["lat"], "lng": spot["lng"],
        "start": start.isoformat(), "end": end.isoformat(),
    })
    data = get_json("https://api.stormglass.io/v2/tide/extremes/point?" + q, headers={"Authorization": key}, attempts=1)
    out = []
    for e in data.get("data", []):
        t = datetime.fromisoformat(e["time"].replace("Z", "+00:00")).astimezone(SAST)
        out.append({"time": t.strftime("%Y-%m-%dT%H:%M"), "type": e.get("type"), "height": round(e.get("height", 0), 2)})
    return out


def round_list(values, digits=1):
    return [None if v is None else round(v, digits) for v in values]


def main():
    old = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                old = json.load(f)
        except Exception:
            old = {}
    old_spots = {s["id"]: s for s in old.get("spots", [])}

    now = datetime.now(SAST)
    key = os.environ.get("STORMGLASS_KEY", "").strip()
    last_tide_day = old.get("tidesFetchedOn")
    fetch_tides = bool(key) and last_tide_day != now.strftime("%Y-%m-%d")

    result = {
        "generated": now.strftime("%Y-%m-%dT%H:%M"),
        "timezone": TZ_NAME,
        "tidesFetchedOn": last_tide_day,
        "spots": [],
    }
    problems = []
    tides_ok = False

    for spot in SPOTS:
        prev = old_spots.get(spot["id"], {})
        entry = {**spot}
        try:
            w = weather(spot)
            h = w["hourly"]
            entry["hours"] = {
                "time": h["time"],
                "temp": round_list(h["temperature_2m"]),
                "wind": round_list(h["wind_speed_10m"]),
                "gust": round_list(h["wind_gusts_10m"]),
                "dir": round_list(h["wind_direction_10m"], 0),
                "rain": round_list(h["precipitation_probability"], 0),
                "visKm": [None if v is None else round(v / 1000, 1) for v in h["visibility"]],
            }
            entry["sun"] = {"date": w["daily"]["time"], "rise": w["daily"]["sunrise"], "set": w["daily"]["sunset"]}
        except Exception as e:  # keep the last good data rather than failing
            problems.append(f"weather {spot['id']}: {e}")
            entry["hours"] = prev.get("hours")
            entry["sun"] = prev.get("sun")
        try:
            m = marine(spot)["hourly"]
            entry["sea"] = {
                "time": m["time"],
                "wave": round_list(m["wave_height"], 1),
                "swell": round_list(m["swell_wave_height"], 1),
                "period": round_list(m["swell_wave_period"], 0),
            }
        except Exception as e:
            problems.append(f"marine {spot['id']}: {e}")
            entry["sea"] = prev.get("sea")
        if fetch_tides:
            try:
                entry["tides"] = tides(spot, key)
                tides_ok = True
            except Exception as e:
                problems.append(f"tides {spot['id']}: {e}")
                entry["tides"] = prev.get("tides", [])
        else:
            entry["tides"] = prev.get("tides", [])
        result["spots"].append(entry)

    if tides_ok:
        result["tidesFetchedOn"] = now.strftime("%Y-%m-%d")
    result["problems"] = problems

    if all(s.get("hours") is None for s in result["spots"]):
        print("No weather data at all - keeping the old file.", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, separators=(",", ":"))
    print(f"Saved {OUT} at {result['generated']}. Problems: {problems or 'none'}")


if __name__ == "__main__":
    main()

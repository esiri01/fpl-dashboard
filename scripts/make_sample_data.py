"""Generate a fake but API-shaped Mech Peeps season in ./sample_data.

Used for offline demo mode and for screenshots:

    python scripts/make_sample_data.py
    FPL_FIXTURES_DIR=sample_data streamlit run fpl_dashboard.py

Names and scores are invented.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fpl.api import fixture_name  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "sample_data"
LEAGUE_ID = 799250
GWS = 8  # GW8 is "current" (live), GW1-7 finished

MANAGERS = [
    ("Tunde A.", "Gear Ratio FC"), ("Chidi O.", "Torque United"), ("Amaka N.", "Flux Capacitors"),
    ("Kelechi E.", "Bernoulli Boys"), ("Femi D.", "Thermo Dynamos"), ("Ngozi U.", "Stress Strain XI"),
    ("Segun B.", "Moment of Inertia"), ("Ifeoma K.", "Fluid Mechanix"), ("Dayo L.", "Cam & Follower"),
    ("Bisi M.", "Heat Sinkers"), ("Obi P.", "Shear Force"), ("Lanre T.", "Piston Broke"),
]
PLAYERS = {1: "Haaland", 2: "Salah", 3: "Palmer", 4: "Saka", 5: "Isak", 6: "Watkins"}
CAP_WEIGHTS = [6, 4, 2, 1, 1, 1]
GLOBAL_AVG = [54, 49, 61, 47, 52, 58, 45, 56]


def write(path: str, payload: dict, params: dict | None = None) -> None:
    (OUT / fixture_name(path, params)).write_text(json.dumps(payload, indent=1))


def main() -> None:
    rng = random.Random(11)
    OUT.mkdir(exist_ok=True)

    # player points per GW (GW8 fixed values)
    player_pts = {gw: {pid: rng.choice([1, 2, 2, 3, 5, 6, 8, 9, 12, 13, 15]) for pid in PLAYERS}
                  for gw in range(1, GWS + 1)}
    player_pts[GWS] = {1: 13, 2: 6, 3: 2, 4: 9, 5: 15, 6: 1}

    seasons = {}
    for i, (name, team) in enumerate(MANAGERS):
        entry = 1000 + i
        skill = rng.uniform(-4, 6)
        chips_left = ["wildcard", "bboost", "3xc", "freehit"]
        rows = []
        for gw in range(1, GWS + 1):
            pts = max(22, min(108, int(rng.gauss(GLOBAL_AVG[gw - 1] + skill + 4, 11))))
            hits = rng.choice([0] * 7 + [4, 4, 8])
            bench = rng.randint(0, 15)
            chip = None
            if gw > 2 and rng.random() < 0.13 and chips_left:
                chip = chips_left.pop(rng.randrange(len(chips_left)))
                if chip == "bboost":
                    pts, bench = pts + bench, 0
                if chip in ("wildcard", "freehit"):
                    hits = 0
            cap = rng.choices(list(PLAYERS), CAP_WEIGHTS)[0]
            rows.append({"gw": gw, "pts": pts, "hits": hits, "bench": bench, "chip": chip, "cap": cap})
        seasons[entry] = (name, team, rows)

    # a few hand-tuned GW8 storylines
    def tweak(manager: str, **kw):
        entry = next(k for k, v in seasons.items() if v[0] == manager)
        seasons[entry][2][GWS - 1].update(kw)

    tweak("Obi P.", pts=65, hits=4)
    tweak("Bisi M.", chip="3xc", cap=5)
    tweak("Dayo L.", chip="bboost", bench=0)
    tweak("Lanre T.", hits=8, pts=60)
    tweak("Tunde A.", cap=6)
    tweak("Chidi O.", cap=5)

    standings, overall = [], 1_500_000
    for entry, (name, team, rows) in seasons.items():
        total, current = 0, []
        for r in rows:
            total += r["pts"] - r["hits"]
            overall = max(50_000, int(overall * rng.uniform(0.82, 1.15)))
            current.append({
                "event": r["gw"], "points": r["pts"], "total_points": total, "rank": overall,
                "rank_sort": overall, "overall_rank": overall, "percentile_rank": 20, "bank": 5,
                "value": 1000, "event_transfers": r["hits"] // 4 + (1 if r["hits"] else 0),
                "event_transfers_cost": r["hits"], "points_on_bench": r["bench"],
            })
            squad = [{"element": pid, "position": pid, "multiplier": 1, "is_captain": False,
                      "is_vice_captain": False, "element_type": 4} for pid in PLAYERS]
            for p in squad:
                if p["element"] == r["cap"]:
                    p.update(is_captain=True, multiplier=3 if r["chip"] == "3xc" else 2)
            vice = next(p for p in squad if not p["is_captain"])
            vice["is_vice_captain"] = True
            write(f"entry/{entry}/event/{r['gw']}/picks/", {
                "active_chip": r["chip"], "automatic_subs": [],
                "entry_history": current[-1], "picks": squad,
            })
        chips = [{"name": r["chip"], "time": "2026-09-01T10:00:00Z", "event": r["gw"]}
                 for r in rows if r["chip"]]
        write(f"entry/{entry}/history/", {"current": current, "past": [], "chips": chips})
        standings.append({"id": entry, "event_total": rows[-1]["pts"] - rows[-1]["hits"],
                          "player_name": name, "rank": 0, "last_rank": 0, "rank_sort": 0,
                          "total": total, "entry": entry, "entry_name": team})

    standings.sort(key=lambda s: -s["total"])
    write(f"leagues-classic/{LEAGUE_ID}/standings/", {
        "league": {"id": LEAGUE_ID, "name": "Mech Peeps", "start_event": 1},
        "standings": {"has_next": False, "page": 1, "results": standings},
        "new_entries": {"has_next": False, "page": 1, "results": []},
    }, {"page_standings": 1})

    events = []
    for gw in range(1, 39):
        played = gw <= GWS
        events.append({
            "id": gw, "name": f"Gameweek {gw}",
            "deadline_time": f"2026-{8 + (gw + 1) // 5:02d}-{(gw * 7) % 27 + 1:02d}T17:30:00Z" if played
            else f"2027-{1 + gw // 8:02d}-01T17:30:00Z",
            "average_entry_score": GLOBAL_AVG[gw - 1] if played else 0,
            "highest_score": 120 if played else None,
            "finished": gw < GWS, "data_checked": gw < GWS,
            "is_current": gw == GWS, "is_next": gw == GWS + 1, "is_previous": gw == GWS - 1,
        })
    chip_rules = [{"id": n, "name": c, "number": 1, "start_event": s, "stop_event": e}
                  for n, (c, s, e) in enumerate(
                      [(c, 1, 19) for c in ("wildcard", "freehit", "bboost", "3xc")]
                      + [(c, 20, 38) for c in ("wildcard", "freehit", "bboost", "3xc")], 1)]
    write("bootstrap-static/", {
        "events": events,
        "elements": [{"id": pid, "web_name": n, "team": pid, "element_type": 4} for pid, n in PLAYERS.items()],
        "teams": [], "total_players": 11_420_000, "chips": chip_rules,
    })
    for gw in range(1, GWS + 1):
        write(f"event/{gw}/live/", {"elements": [
            {"id": pid, "stats": {"minutes": 90, "total_points": player_pts[gw][pid]}, "explain": []}
            for pid in PLAYERS
        ]})
    print(f"Wrote {len(list(OUT.glob('*.json')))} files to {OUT}")


if __name__ == "__main__":
    main()

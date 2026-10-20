"""All dashboard calculations, as pure pandas functions.

DataFrames in, DataFrames out. No network, no Streamlit, so every rule here is unit-tested.

Ranking convention (same as FPL): ties share a place and the next place is skipped,
e.g. 61, 61, 60 -> 4=, 4=, 6. The podium is the exception: it uses the top three
*distinct* scores so tied managers share a step.
"""

from __future__ import annotations

import math

import pandas as pd

from fpl.config import chip_label

SEASON_COLUMNS = [
    "entry", "manager", "team", "gw", "points", "hits", "net_points", "total_points",
    "league_points", "bench_points", "transfers", "overall_rank", "chip",
    "league_rank", "league_rank_label", "prev_league_rank", "movement",
]


# ---------------------------------------------------------------- ranking helpers
def competition_rank(scores: pd.Series) -> pd.Series:
    """Highest score = 1; ties share a place and the next is skipped (1, 2, 2, 4)."""
    return scores.rank(method="min", ascending=False).astype(int)


def rank_labels(ranks: pd.Series) -> pd.Series:
    """'4=' for tied places, '4' otherwise."""
    tied = ranks.duplicated(keep=False)
    return ranks.astype(str) + tied.map({True: "=", False: ""})


def ordinal(n: int | float | None) -> str:
    """1 -> '1st', 22 -> '22nd'."""
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return "–"
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# ---------------------------------------------------------------- core frames
def managers_frame(standings: list[dict]) -> pd.DataFrame:
    """One row per manager from the league standings response."""
    rows = [
        {
            "entry": int(m["entry"]),
            "manager": m.get("player_name") or f"Manager {m['entry']}",
            "team": m.get("entry_name") or "",
        }
        for m in standings
        if m.get("entry") is not None
    ]
    return pd.DataFrame(rows, columns=["entry", "manager", "team"])


def build_season_frame(
    managers: pd.DataFrame, histories: dict[int, dict], start_event: int = 1
) -> pd.DataFrame:
    """Tidy frame: one row per (manager, gameweek) from each manager's history.

    ``league_points`` is the running total of net points from the league's start
    gameweek, which is what the league table ranks on.
    """
    rows = []
    for entry, hist in histories.items():
        chips = {c.get("event"): c.get("name") for c in (hist.get("chips") or [])}
        for gw in hist.get("current") or []:
            points = int(gw.get("points") or 0)
            hits = int(gw.get("event_transfers_cost") or 0)
            rows.append(
                {
                    "entry": int(entry),
                    "gw": int(gw["event"]),
                    "points": points,
                    "hits": hits,
                    "net_points": points - hits,
                    "total_points": int(gw.get("total_points") or 0),
                    "bench_points": int(gw.get("points_on_bench") or 0),
                    "transfers": int(gw.get("event_transfers") or 0),
                    "overall_rank": gw.get("overall_rank"),
                    "chip": chips.get(gw["event"]),
                }
            )
    if not rows:
        return pd.DataFrame(columns=SEASON_COLUMNS)

    df = pd.DataFrame(rows).merge(managers, on="entry", how="inner")
    df = df[df["gw"] >= start_event].sort_values(["entry", "gw"]).reset_index(drop=True)
    df["league_points"] = df.groupby("entry")["net_points"].cumsum()
    df["league_rank"] = df.groupby("gw")["league_points"].transform(competition_rank)
    df["league_rank_label"] = df.groupby("gw")["league_rank"].transform(rank_labels)
    df["prev_league_rank"] = df.groupby("entry")["league_rank"].shift(1)
    df["movement"] = (df["prev_league_rank"] - df["league_rank"]).fillna(0).astype(int)
    return df[SEASON_COLUMNS]


def upto(season: pd.DataFrame, gw: int) -> pd.DataFrame:
    """Season frame limited to gameweeks <= gw."""
    return season[season["gw"] <= gw]


# ---------------------------------------------------------------- gameweek view
def gameweek_table(season: pd.DataFrame, gw: int) -> pd.DataFrame:
    """Everyone's result for one gameweek, best net score first."""
    t = season[season["gw"] == gw].copy()
    if t.empty:
        return t
    t["gw_rank"] = competition_rank(t["net_points"])
    t["gw_rank_label"] = rank_labels(t["gw_rank"])
    t["chip_name"] = t["chip"].map(chip_label)
    return t.sort_values(["gw_rank", "manager"]).reset_index(drop=True)


def podium(table: pd.DataFrame) -> list[dict]:
    """Top three distinct net scores; tied managers share a step.

    Returns ``[{"place": 1, "score": 77, "rows": DataFrame}, ...]``.
    """
    if table.empty:
        return []
    scores = sorted(table["net_points"].unique(), reverse=True)[:3]
    return [
        {"place": i + 1, "score": int(s), "rows": table[table["net_points"] == s]}
        for i, s in enumerate(scores)
    ]


def movers(table: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Biggest league-table climb and drop this gameweek (all tied managers included)."""
    out = {"climb": table.iloc[0:0], "drop": table.iloc[0:0]}
    if table.empty or table["prev_league_rank"].isna().all():
        return out
    best, worst = table["movement"].max(), table["movement"].min()
    if best > 0:
        out["climb"] = table[table["movement"] == best]
    if worst < 0:
        out["drop"] = table[table["movement"] == worst]
    return out


def captain_frame(
    picks: dict[int, dict],
    live: dict | None,
    player_names: dict[int, str],
    gw_finished: bool,
) -> pd.DataFrame:
    """Each manager's captain and what the armband returned.

    If the gameweek is finished and the captain played 0 minutes, the vice-captain
    is used (that's how FPL scores it).
    """
    pts, mins = {}, {}
    for el in (live or {}).get("elements") or []:
        stats = el.get("stats") or {}
        pts[el["id"]] = stats.get("total_points", 0)
        mins[el["id"]] = stats.get("minutes", 0)

    rows = []
    for entry, data in picks.items():
        squad = data.get("picks") or []
        cap = next((p for p in squad if p.get("is_captain")), None)
        if cap is None:
            continue
        vice = next((p for p in squad if p.get("is_vice_captain")), None)
        multiplier = int(cap.get("multiplier") or 2)
        if multiplier < 2:  # defensive: captain multiplier should be 2 or 3
            multiplier = 3 if data.get("active_chip") == "3xc" else 2
        chosen, used_vice = cap, False
        if gw_finished and live and mins.get(cap["element"], 0) == 0 and vice is not None \
                and mins.get(vice["element"], 0) > 0:
            chosen, used_vice = vice, True
        base = pts.get(chosen["element"]) if live else None
        rows.append(
            {
                "entry": int(entry),
                "captain_id": cap["element"],
                "captain": player_names.get(cap["element"], f"#{cap['element']}"),
                "scored_by": player_names.get(chosen["element"], f"#{chosen['element']}"),
                "used_vice": used_vice,
                "multiplier": multiplier,
                "active_chip": data.get("active_chip"),
                "captain_points": base,
                "captain_return": None if base is None else base * multiplier,
            }
        )
    return pd.DataFrame(
        rows,
        columns=["entry", "captain_id", "captain", "scored_by", "used_vice", "multiplier",
                 "active_chip", "captain_points", "captain_return"],
    )


def captain_summary(caps: pd.DataFrame) -> pd.DataFrame:
    """Captains picked across the league: how many managers, and their points."""
    if caps.empty:
        return pd.DataFrame(columns=["captain", "managers", "points", "doubled"])
    g = (
        caps.groupby("captain", as_index=False)
        .agg(managers=("entry", "count"), points=("captain_points", "first"))
        .sort_values(["managers", "points"], ascending=[False, False], na_position="last")
        .reset_index(drop=True)
    )
    g["doubled"] = g["points"].map(lambda p: None if pd.isna(p) else int(p) * 2)
    return g


# ---------------------------------------------------------------- season view
def weekly_winners(season: pd.DataFrame) -> pd.DataFrame:
    """Winner(s) of each gameweek on net points (ties all count)."""
    if season.empty:
        return season.iloc[0:0]
    best = season.groupby("gw")["net_points"].transform("max")
    return season[season["net_points"] == best][["gw", "entry", "manager", "net_points"]]


def wins_tally(season: pd.DataFrame) -> pd.DataFrame:
    """Gameweeks won per manager, most first."""
    w = weekly_winners(season)
    if w.empty:
        return pd.DataFrame(columns=["manager", "wins", "gws"])
    t = (
        w.sort_values("gw")
        .groupby("manager")
        .agg(wins=("gw", "count"), gws=("gw", lambda s: ", ".join(f"GW{g}" for g in s)))
        .reset_index()
        .sort_values(["wins", "manager"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return t


def gap_to_leader(season: pd.DataFrame) -> pd.DataFrame:
    """Points behind the league leader after each gameweek (0 = leading)."""
    df = season[["gw", "entry", "manager", "league_points", "league_rank"]].copy()
    df["gap"] = df.groupby("gw")["league_points"].transform("max") - df["league_points"]
    return df


def league_average(season: pd.DataFrame) -> pd.DataFrame:
    """Mean net score in the league for each gameweek."""
    return season.groupby("gw", as_index=False)["net_points"].mean().rename(
        columns={"net_points": "league_avg"}
    )


def season_stats(season: pd.DataFrame) -> pd.DataFrame:
    """One row per manager: totals, averages, best/worst, consistency, hits, bench, chips."""
    if season.empty:
        return pd.DataFrame()
    last_gw = season["gw"].max()
    latest = season[season["gw"] == last_gw].set_index("entry")
    wins = weekly_winners(season).groupby("entry").size()
    leader = latest["league_points"].max()

    rows = []
    for entry, g in season.groupby("entry"):
        g = g.sort_values("gw")
        best = g.loc[g["net_points"].idxmax()]
        worst = g.loc[g["net_points"].idxmin()]
        chips = [f"{chip_label(c)} (GW{gw})" for gw, c in zip(g["gw"], g["chip"], strict=False) if isinstance(c, str) and c]
        total = int(latest.loc[entry, "league_points"]) if entry in latest.index else int(
            g["league_points"].iloc[-1]
        )
        rows.append(
            {
                "entry": entry,
                "manager": g["manager"].iloc[0],
                "team": g["team"].iloc[0],
                "rank": latest.loc[entry, "league_rank"] if entry in latest.index else None,
                "total": total,
                "behind": int(leader - total),
                "avg": round(g["net_points"].mean(), 1),
                "best": int(best["net_points"]),
                "best_gw": int(best["gw"]),
                "worst": int(worst["net_points"]),
                "worst_gw": int(worst["gw"]),
                "consistency": round(g["net_points"].std(ddof=0), 1),
                "gw_wins": int(wins.get(entry, 0)),
                "hits": int(g["hits"].sum()),
                "bench": int(g["bench_points"].sum()),
                "chips": ", ".join(chips),
            }
        )
    out = pd.DataFrame(rows).sort_values(["total", "manager"], ascending=[False, True])
    out["rank"] = competition_rank(out["total"])
    out["rank_label"] = rank_labels(out["rank"])
    return out.reset_index(drop=True)


def awards(stats: pd.DataFrame) -> dict[str, pd.Series]:
    """Fun season awards from the stats table (needs at least 2 gameweeks to be meaningful)."""
    if stats.empty:
        return {}
    return {
        "consistent": stats.sort_values(["consistency", "total"], ascending=[True, False]).iloc[0],
        "bench": stats.sort_values(["bench", "total"], ascending=[False, True]).iloc[0],
        "hits": stats.sort_values(["hits", "total"], ascending=[False, True]).iloc[0],
    }

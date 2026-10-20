"""Manager tab: one manager's season in detail."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fpl import charts, data, metrics
from fpl.config import chip_label
from fpl.ui import Context, e, html


def _fmt_overall(rank) -> str:
    if rank is None or pd.isna(rank):
        return "–"
    rank = int(rank)
    if rank >= 1_000_000:
        return f"{rank / 1_000_000:.2f}M"
    if rank >= 10_000:
        return f"{rank / 1_000:.0f}k"
    return f"{rank:,}"


def _chips(ctx: Context, history: pd.DataFrame) -> None:
    st.subheader("Chips")
    used = history[history["chip"].notna()][["gw", "chip", "net_points"]]
    rules = ctx.chip_rules
    boxes = []
    if rules:
        # Seasons with two sets of chips: each rule has a name and a start/stop gameweek window.
        for rule in sorted(rules, key=lambda r: (r.get("start_event", 0), r.get("name", ""))):
            name, start, stop = rule.get("name"), rule.get("start_event", 1), rule.get("stop_event", 38)
            hit = used[(used["chip"] == name) & used["gw"].between(start, stop)]
            if not hit.empty:
                r = hit.iloc[0]
                boxes.append((chip_label(name), f"Used GW{r['gw']} · {r['net_points']} pts", True))
            elif ctx.gw > stop:
                boxes.append((chip_label(name), f"Expired (GW{start}–{stop})", True))
            else:
                boxes.append((chip_label(name), f"Available until GW{stop}", False))
    else:
        for _, r in used.iterrows():
            boxes.append((chip_label(r["chip"]), f"Used GW{r['gw']} · {r['net_points']} pts", True))
    if not boxes:
        st.caption("No chips played yet.")
        return
    cols = st.columns(2)
    for i, (title, sub, done) in enumerate(boxes):
        with cols[i % 2]:
            colour = "#5B6660" if done else "#1F7A4D"
            html(
                f'<div class="pf-chipbox{" used" if done else ""}"><b>{e(title)}</b>'
                f'<div style="font-size:.85rem;color:{colour};font-weight:600">{e(sub)}</div></div>'
            )


def _captain_history(ctx: Context, entry: int, history: pd.DataFrame) -> None:
    st.subheader("Captain history")
    gws = tuple(int(g) for g in sorted(history["gw"], reverse=True))
    picks = data.load_entry_picks_by_gw(entry, gws)
    finished = {ev["id"]: bool(ev.get("finished")) for ev in ctx.events}
    rows = []
    for gw in gws:
        if gw not in picks:
            continue
        live = data.load_live(gw, finished.get(gw, False))
        cf = metrics.captain_frame({entry: picks[gw]}, live, ctx.players, finished.get(gw, False))
        if cf.empty:
            continue
        r = cf.iloc[0]
        rows.append(
            {
                "GW": gw,
                "Captain": r["captain"] + (" (TC)" if r["multiplier"] == 3 else "")
                + (f" → {r['scored_by']} (VC)" if r["used_vice"] else ""),
                "Player pts": r["captain_points"],
                "Captain return": r["captain_return"],
            }
        )
    if not rows:
        st.caption("Captain picks unavailable.")
        return
    df = pd.DataFrame(rows)
    total = pd.to_numeric(df["Captain return"], errors="coerce").sum()
    fav = df["Captain"].str.replace(r" \(.*", "", regex=True).value_counts()
    st.caption(f"{int(total)} captain points · favourite: {fav.index[0]} ({fav.iloc[0]} of {len(df)} weeks)")
    st.dataframe(df, hide_index=True, width="stretch", height=min(38 + 35 * len(df), 420))


def render(ctx: Context) -> None:
    season = metrics.upto(ctx.season, ctx.gw)
    if season.empty:
        st.info("No gameweeks have been scored yet.")
        return

    latest_gw = season["gw"].max()
    order = season[season["gw"] == latest_gw].sort_values(["league_rank", "manager"])
    options = order["entry"].tolist()
    labels = dict(zip(order["entry"], order["manager"] + " — " + order["team"], strict=False))
    entry = st.selectbox("Manager", options, format_func=labels.get, key="manager_entry")

    history = season[season["entry"] == entry].sort_values("gw")
    stats = metrics.season_stats(season).set_index("entry").loc[entry]
    now = history.iloc[-1]

    st.caption(
        f"Avg {stats['avg']} / GW · {stats['gw_wins']} GW win{'s' if stats['gw_wins'] != 1 else ''} · "
        f"−{stats['hits']} in hits · {stats['bench']} bench pts"
    )
    c1, c2, c3, c4 = st.columns(4)
    mv = int(now["movement"])
    c1.metric(
        "League position",
        metrics.ordinal(now["league_rank"]) + ("=" if now["league_rank_label"].endswith("=") else ""),
        delta=f"{mv:+d} place{'s' if abs(mv) != 1 else ''} this GW" if mv else "No change this GW",
        delta_color="normal" if mv else "off",
        delta_arrow="auto" if mv else "off",
        border=True,
    )
    c2.metric(
        "Total points",
        int(now["league_points"]),
        delta=f"{stats['behind']} behind the leader" if stats["behind"] else "Leading the league",
        delta_color="off", delta_arrow="off",
        border=True,
    )
    total_players = f"of {ctx.total_players / 1_000_000:.1f}M players" if ctx.total_players else None
    c3.metric("Overall FPL rank", _fmt_overall(now["overall_rank"]), delta=total_players,
              delta_color="off", delta_arrow="off", border=True)
    c4.metric(
        "Best gameweek",
        stats["best"],
        delta=f"GW{stats['best_gw']} · worst {stats['worst']} (GW{stats['worst_gw']})",
        delta_color="off", delta_arrow="off",
        border=True,
    )

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Points per gameweek")
        st.caption("Bars: net points · dashed line: league average")
        st.altair_chart(charts.manager_points(history, metrics.league_average(season)), width="stretch")
    with right:
        st.subheader("League position over time")
        st.caption(" ")
        st.altair_chart(charts.manager_rank(history, ctx.n_managers), width="stretch")

    left, right = st.columns([3, 2], gap="large")
    with left:
        _captain_history(ctx, int(entry), history)
    with right:
        _chips(ctx, history)

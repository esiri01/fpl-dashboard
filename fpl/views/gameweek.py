"""Gameweek tab: KPIs, podium, movers, full results table and captaincy."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fpl import data, metrics
from fpl.ui import Context, e, html, movement_text, names


def _kpis(ctx: Context, table: pd.DataFrame) -> None:
    avg = table["net_points"].mean()
    global_avg = ctx.event.get("average_entry_score")
    top = table[table["net_points"] == table["net_points"].max()]
    chips = table[table["chip"].notna()]
    hits = int(table["hits"].sum())
    hit_takers = int((table["hits"] > 0).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "League average",
        f"{avg:.1f}",
        delta=f"{avg - global_avg:+.1f} vs FPL average ({global_avg})" if global_avg else None,
        border=True,
    )
    c2.metric("Highest score", int(top["net_points"].iloc[0]), delta=names(top), delta_color="off",
              delta_arrow="off", border=True)
    c3.metric(
        "Chips played",
        len(chips),
        delta=" · ".join(sorted(set(chips["chip_name"]))) or "None this week",
        delta_color="off", delta_arrow="off",
        border=True,
    )
    c4.metric(
        "Transfer hits taken",
        f"−{hits}" if hits else "0",
        delta=f"{hit_takers} of {len(table)} managers took a hit",
        delta_color="off", delta_arrow="off",
        border=True,
    )


def _podium_card(step: dict) -> str:
    place = step["place"]
    css = {1: "gold", 2: "silver", 3: "bronze"}[place]
    label = {1: "1st · GW winner", 2: "2nd", 3: "3rd"}[place]
    rows = step["rows"]
    first = rows.iloc[0]
    if len(rows) == 1:
        how = []
        if first["hits"]:
            how.append(f"{first['points']} − {first['hits']} hit")
        if first["chip_name"]:
            how.append(first["chip_name"])
        who = f'<div class="pf-name">{e(first["manager"])}</div><div class="pf-sub">{e(first["team"])}</div>'
        detail = " · ".join(how) or "pts"
    else:
        who = f'<div class="pf-name">{e(names(rows))}</div><div class="pf-sub">Tied</div>'
        detail = "pts each"
    return (
        f'<div class="pf-card {css}"><div class="pf-label {css}">{label}</div>{who}'
        f'<div><span class="pf-big">{step["score"]}</span> <span class="pf-sub">{e(detail)}</span></div></div>'
    )


def _movers_card(mv: dict) -> str:
    def line(rows: pd.DataFrame, cls: str) -> str:
        if rows.empty:
            return '<div class="pf-sub">Nobody</div>'
        m = int(rows["movement"].iloc[0])
        sign = "+" if m > 0 else "−"
        to = rows["league_rank_label"].iloc[0]
        return (
            f'<div style="font-weight:600">{e(names(rows))} '
            f'<span class="{cls}">{"▲" if m > 0 else "▼"} {sign}{abs(m)} → {e(to)}</span></div>'
        )

    return (
        '<div class="pf-card"><div class="pf-label">League table movers</div>'
        '<div class="pf-sub" style="margin-top:.6rem">Biggest climb</div>'
        f'{line(mv["climb"], "pf-up")}'
        '<div class="pf-sub" style="margin-top:.6rem">Biggest drop</div>'
        f'{line(mv["drop"], "pf-down")}</div>'
    )


def _results_table(table: pd.DataFrame) -> None:
    top = table["net_points"].max()
    bottom = table["net_points"].min()
    show = pd.DataFrame(
        {
            "#": table["gw_rank_label"],
            "Manager": table["manager"],
            "Team": table["team"],
            "Pts": table["points"],
            "Hits": table["hits"].map(lambda h: f"−{h}" if h else "0"),
            "Net": table["net_points"],
            "Captain": table.get("captain_display", pd.Series([""] * len(table))),
            "Chip": table["chip_name"],
            "League": table["league_rank_label"],
            "Move": table["movement"].map(movement_text),
        }
    )
    is_top = (table["net_points"] == top).to_list()
    is_bottom = ((table["net_points"] == bottom) & (top != bottom)).to_list()

    def row_style(row):
        i = row.name
        if is_top[i]:
            return ["background-color: #FBF6E8"] * len(row)
        if is_bottom[i]:
            return ["background-color: #FCF4F0"] * len(row)
        return [""] * len(row)

    def move_style(v: str):
        if v.startswith("▲"):
            return "color: #1F7A4D; font-weight: 600"
        if v.startswith("▼"):
            return "color: #A63B28; font-weight: 600"
        return "color: #8A938E"

    styled = (
        show.style.apply(row_style, axis=1)
        .map(move_style, subset=["Move"])
        .set_properties(subset=["Net"], **{"font-weight": "700"})
    )
    st.dataframe(
        styled,
        hide_index=True,
        width="stretch",
        height=min(38 + 35 * len(show), 720),
        column_config={
            "#": st.column_config.TextColumn(width="small"),
            "Pts": st.column_config.NumberColumn(width="small"),
            "Hits": st.column_config.TextColumn(width="small"),
            "Chip": st.column_config.TextColumn(width="medium"),
            "Net": st.column_config.NumberColumn(width="small", help="Points minus transfer hits"),
            "League": st.column_config.TextColumn(width="small", help="League position after this GW"),
            "Move": st.column_config.TextColumn(width="small", help="Places gained/lost this GW"),
        },
    )
    winners = table[table["net_points"] == top]
    caption = f"Highlighted: GW winner{'s' if len(winners) > 1 else ''} ({names(winners)})"
    if top != bottom:
        caption += f" and the wooden spoon ({names(table[table['net_points'] == bottom])})."
    st.caption(caption + " Ranked on net points (after transfer hits). Click a column header to sort.")


def _captaincy(caps: pd.DataFrame, table: pd.DataFrame) -> None:
    st.subheader("Captaincy")
    if caps.empty:
        st.info("Captain picks aren't available for this gameweek yet.")
        return
    st.caption("Who the league backed, and what the armband returned (player points → doubled)")
    summary = metrics.captain_summary(caps)
    most = int(summary["managers"].max())
    bars_col, calls_col = st.columns([3, 2], gap="large")
    with bars_col:
        for _, row in summary.iterrows():
            n = int(row["managers"])
            pts = "–" if pd.isna(row["points"]) else f"{int(row['points'])} → {row['doubled']} pts"
            st.progress(
                n / most,
                text=f"**{row['captain']}** · {n} manager{'s' if n != 1 else ''} · {pts}",
            )

    scored = caps.dropna(subset=["captain_return"]).merge(table[["entry", "manager"]], on="entry")
    if scored.empty:
        return
    best = scored[scored["captain_return"] == scored["captain_return"].max()]
    worst = scored[scored["captain_return"] == scored["captain_return"].min()]

    def call(rows: pd.DataFrame) -> str:
        r = rows.iloc[0]
        tag = " (TC)" if r["multiplier"] == 3 else ""
        vice = f" → {r['scored_by']} (VC)" if r["used_vice"] else ""
        return f"{e(names(rows))}<br>{e(r['captain'])}{tag}{e(vice)} · {int(r['captain_return'])} pts"

    with calls_col:
        c1, c2 = st.columns(2)
        with c1:
            html(f'<div class="pf-callout good"><div class="pf-label" style="color:#155C39">Best call</div>{call(best)}</div>')
        with c2:
            html(f'<div class="pf-callout bad"><div class="pf-label" style="color:#7E2E1E">Worst call</div>{call(worst)}</div>')


def render(ctx: Context) -> None:
    table = metrics.gameweek_table(ctx.season, ctx.gw)
    if table.empty:
        st.info(f"No scores for Gameweek {ctx.gw} yet. Check back after the first match kicks off.")
        return

    # Captains: one picks call per manager for this GW (cached), plus live player points.
    entries = tuple(int(x) for x in table["entry"])
    picks, failed = data.load_picks(entries, ctx.gw, ctx.finished)
    live = data.load_live(ctx.gw, ctx.finished)
    caps = metrics.captain_frame(picks, live, ctx.players, ctx.finished)
    if not caps.empty:
        caps["captain_display"] = caps.apply(
            lambda r: r["captain"] + (" (TC)" if r["multiplier"] == 3 else ""), axis=1
        )
        table = table.merge(caps[["entry", "captain_display"]], on="entry", how="left")
    if failed:
        who = table[table["entry"].isin(failed)]["manager"].tolist()
        st.warning(f"Couldn't load captain picks for: {', '.join(who)}.")

    _kpis(ctx, table)

    steps = metrics.podium(table)
    cols = st.columns(4)
    for col, step in zip(cols, steps, strict=False):
        with col:
            html(_podium_card(step))
    with cols[3]:
        html(_movers_card(metrics.movers(table)))

    st.write("")
    st.subheader(f"Gameweek {ctx.gw} results")
    _results_table(table)
    st.write("")
    _captaincy(caps, table)

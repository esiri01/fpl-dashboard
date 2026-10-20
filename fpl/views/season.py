"""Season tab: points race, league position, weekly wins, awards and season stats."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fpl import charts, metrics
from fpl.ui import Context, e, html

SHORT_CHIPS = {
    r"Wildcard \(": "WC (", r"Free Hit \(": "FH (", r"Bench Boost \(": "BB (",
    r"Triple Captain \(": "TC (", r"Assistant Manager \(": "AM (",
}


def render(ctx: Context) -> None:
    season = metrics.upto(ctx.season, ctx.gw)
    if season.empty:
        st.info("No gameweeks have been scored yet.")
        return

    gws = sorted(season["gw"].unique())
    latest = season[season["gw"] == gws[-1]].sort_values(["league_rank", "manager"])
    top4 = latest["manager"].head(4).tolist()
    leader = latest.iloc[0]

    if len(gws) < 2:
        st.info("The season charts fill in after two gameweeks. Stats so far are below.")
    else:
        head_l, head_r = st.columns([3, 1])
        head_l.subheader("Points race")
        head_l.caption("Points behind the leader after each gameweek. Top 4 coloured; hover a line to isolate a manager.")
        head_r.markdown(
            f"<div style='text-align:right;padding-top:1.4rem'>Leader: <b>{e(leader['manager'])} · "
            f"{int(leader['league_points'])} pts</b></div>",
            unsafe_allow_html=True,
        )
        st.altair_chart(charts.points_race(metrics.gap_to_leader(season), top4), width="stretch")

        left, right = st.columns([2, 1], gap="large")
        with left:
            st.subheader("League position")
            st.caption("Position in the league after each gameweek (1st at the top)")
            st.altair_chart(charts.league_position(season, top4), width="stretch")
        with right:
            st.subheader("Manager of the Week")
            st.caption("Gameweeks won (ties count for everyone tied)")
            tally = metrics.wins_tally(season)
            st.altair_chart(charts.wins_bar(tally), width="stretch")
            no_wins = sorted(set(season["manager"]) - set(tally["manager"]))
            if no_wins:
                st.caption("No wins yet: " + ", ".join(no_wins))

    stats = metrics.season_stats(season)
    aw = metrics.awards(stats)
    if aw and len(gws) >= 2:
        c1, c2, c3 = st.columns(3)
        with c1:
            r = aw["consistent"]
            html(
                '<div class="pf-card"><div class="pf-label" style="color:#155C39">Mr/Ms Consistent</div>'
                f'<div class="pf-name">{e(r["manager"])}</div>'
                f'<div class="pf-sub">Steadiest scorer (σ {r["consistency"]}). Never below {r["worst"]}.</div></div>'
            )
        with c2:
            r = aw["bench"]
            html(
                '<div class="pf-card"><div class="pf-label gold">Bench warmer</div>'
                f'<div class="pf-name">{e(r["manager"])}</div>'
                f'<div class="pf-sub">{r["bench"]} points left on the bench this season.</div></div>'
            )
        with c3:
            r = aw["hits"]
            html(
                '<div class="pf-card"><div class="pf-label" style="color:#7E2E1E">Hit-taker of the season</div>'
                f'<div class="pf-name">{e(r["manager"])}</div>'
                f'<div class="pf-sub">−{r["hits"]} pts in transfer hits.</div></div>'
            )
        st.write("")

    st.subheader("Season stats")
    st.caption(f"Gameweeks {gws[0]}–{gws[-1]} · Consistency = standard deviation of weekly scores (lower is steadier)")
    show = pd.DataFrame(
        {
            "#": stats["rank_label"],
            "Manager": stats["manager"],
            "Total": stats["total"],
            "Behind": stats["behind"].map(lambda b: f"−{b}" if b else "–"),
            "Avg": stats["avg"],
            "Best": stats.apply(lambda r: f"{r['best']} (GW{r['best_gw']})", axis=1),
            "Worst": stats.apply(lambda r: f"{r['worst']} (GW{r['worst_gw']})", axis=1),
            "Consistency": stats["consistency"],
            "GW wins": stats["gw_wins"],
            "Hits": stats["hits"].map(lambda h: f"−{h}" if h else "0"),
            "Bench pts": stats["bench"],
            "Chips used": stats["chips"].replace(SHORT_CHIPS, regex=True).replace("", "–"),
        }
    )
    st.dataframe(
        show,
        hide_index=True,
        width="stretch",
        height=min(38 + 35 * len(show), 760),
        column_config={
            "#": st.column_config.TextColumn(width="small"),
            "Avg": st.column_config.NumberColumn(format="%.1f"),
            "Consistency": st.column_config.NumberColumn(format="%.1f", help="Std dev of weekly net scores"),
            "Chips used": st.column_config.TextColumn(
                width="medium", help="WC Wildcard · FH Free Hit · BB Bench Boost · TC Triple Captain"
            ),
        },
    )

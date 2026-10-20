"""Mech Peeps FPL dashboard — Streamlit entry point.

Run locally:  streamlit run fpl_dashboard.py
"""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from fpl import config, data, metrics
from fpl.api import FPLError, NotFound
from fpl.ui import Context, e, html, inject_css
from fpl.views import gameweek, manager, season

st.set_page_config(page_title="Mech Peeps FPL", page_icon="🏆", layout="wide")
inject_css()

LEAGUE_ID = config.get_league_id()


def fail(message: str) -> None:
    st.error(message)
    st.stop()


# ---------------------------------------------------------------- load shared data
try:
    boot = data.load_bootstrap()
    league, standings = data.load_league(LEAGUE_ID)
except NotFound:
    fail(f"League {LEAGUE_ID} wasn't found. Check the league ID in the app settings.")
except FPLError as exc:
    fail(f"Couldn't load data from the FPL website: {exc} Try **Refresh data** in a minute.")

gws = data.available_gameweeks(boot["events"])

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("## 🏆 Mech Peeps FPL")
    if not gws:
        st.caption("The season hasn't started yet.")
    else:
        current = next((g for g in gws if g.get("is_current")), gws[-1])
        labels = {g["id"]: g.get("name") or f"Gameweek {g['id']}" for g in gws}
        options = [g["id"] for g in reversed(gws)]
        gw = st.selectbox(
            "Gameweek",
            options,
            index=options.index(current["id"]),
            format_func=lambda i: labels[i] + (" (current)" if i == current["id"] else ""),
        )
        event = next(g for g in gws if g["id"] == gw)
        status = data.gameweek_status(event)
        dot = {"Live": "🟢", "Provisional": "🟡", "Final": "✅"}[status]
        st.markdown(f"**{dot} GW {gw} · {status}**")
        refresh_note = "refreshes every 5 min while live" if status != "Final" else "final scores"
        st.caption(f"Last updated {datetime.now(UTC).strftime('%H:%M')} UTC · {refresh_note}")

    if st.button("↻ Refresh data", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.caption("Data from the public FPL API (unofficial).")
    if config.get_fixtures_dir():
        st.warning("Offline demo mode: showing saved sample data.")

if not gws:
    st.info("No gameweeks have started yet. The dashboard fills in after the GW1 deadline.")
    st.stop()

# ---------------------------------------------------------------- season data
managers = metrics.managers_frame(standings)
if managers.empty:
    fail("This league has no managers yet.")

histories, failed = data.load_histories(tuple(int(x) for x in managers["entry"]))
season_df = metrics.build_season_frame(managers, histories, int(league.get("start_event") or 1))
if failed:
    who = managers[managers["entry"].isin(failed)]["manager"].tolist()
    st.warning(f"Couldn't load {len(who)} manager(s), so they're missing below: {', '.join(who)}.")

ctx = Context(
    league_id=LEAGUE_ID,
    league=league,
    season=season_df,
    gw=gw,
    event=event,
    status=status,
    players=boot["players"],
    total_players=boot["total_players"],
    n_managers=len(managers),
    events=boot["events"],
    chip_rules=boot["chips"],
)

# ---------------------------------------------------------------- header + tabs
left, right = st.columns([3, 2])
with left:
    html(f'<div class="pf-eyebrow">Classic league · {e(LEAGUE_ID)}</div>')
    st.title(league.get("name") or "Mech Peeps")
with right:
    html(
        '<div class="pf-chips">'
        f'<span class="pf-chip">Gameweek {gw}</span>'
        f'<span class="pf-chip">{len(managers)} managers</span>'
        "</div>"
    )

tab_gw, tab_season, tab_manager = st.tabs(["🗓️ Gameweek", "📈 Season", "👤 Manager"])
with tab_gw:
    gameweek.render(ctx)
with tab_season:
    season.render(ctx)
with tab_manager:
    manager.render(ctx)

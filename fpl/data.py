"""Cached data loading for the Streamlit app.

Every FPL request goes through here, so each piece of data is fetched once per TTL:
- live / current-gameweek data: 5 minutes
- finished gameweeks: 24 hours
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fpl import config
from fpl.api import FPLClient, fetch_many


@st.cache_resource
def get_client() -> FPLClient:
    return FPLClient(fixtures_dir=config.get_fixtures_dir())


@st.cache_data(ttl=config.TTL_BOOTSTRAP, show_spinner="Loading gameweeks…")
def load_bootstrap() -> dict:
    data = get_client().bootstrap()
    return {
        "events": data.get("events") or [],
        "players": {el["id"]: el.get("web_name", f"#{el['id']}") for el in data.get("elements") or []},
        "total_players": data.get("total_players"),
        # Chip windows (name, start_event, stop_event), when the API provides them.
        "chips": data.get("chips") or [],
    }


@st.cache_data(ttl=config.TTL_LIVE, show_spinner="Loading league…")
def load_league(league_id: str) -> tuple[dict, list[dict]]:
    return get_client().league_standings(league_id)


@st.cache_data(ttl=config.TTL_LIVE, show_spinner="Loading every manager's season…")
def load_histories(entry_ids: tuple[int, ...]) -> tuple[dict[int, dict], dict[int, str]]:
    """One /history/ call per manager covers the whole season."""
    return fetch_many(get_client().entry_history, entry_ids)


def _fetch_picks(entry_ids: tuple[int, ...], gw: int) -> tuple[dict[int, dict], dict[int, str]]:
    client = get_client()
    return fetch_many(lambda e: client.entry_picks(e, gw), entry_ids)


@st.cache_data(ttl=config.TTL_FINISHED, show_spinner="Loading captains…")
def _picks_finished(entry_ids: tuple[int, ...], gw: int):
    return _fetch_picks(entry_ids, gw)


@st.cache_data(ttl=config.TTL_LIVE, show_spinner="Loading captains…")
def _picks_live(entry_ids: tuple[int, ...], gw: int):
    return _fetch_picks(entry_ids, gw)


def load_picks(entry_ids: tuple[int, ...], gw: int, finished: bool):
    """Every manager's picks for one gameweek -> (results, failures)."""
    return (_picks_finished if finished else _picks_live)(entry_ids, gw)


@st.cache_data(ttl=config.TTL_FINISHED, show_spinner=False)
def _live_finished(gw: int) -> dict:
    return get_client().event_live(gw)


@st.cache_data(ttl=config.TTL_LIVE, show_spinner=False)
def _live_current(gw: int) -> dict:
    return get_client().event_live(gw)


def load_live(gw: int, finished: bool) -> dict | None:
    """Player points for a gameweek; None if unavailable (captain returns then show '–')."""
    try:
        return (_live_finished if finished else _live_current)(gw)
    except Exception:  # noqa: BLE001 - captain points are a nice-to-have
        return None


@st.cache_data(ttl=config.TTL_LIVE, show_spinner="Loading this manager's captains…")
def load_entry_picks_by_gw(entry: int, gws: tuple[int, ...]) -> dict[int, dict]:
    """One manager's picks for several gameweeks (Manager tab captain history)."""
    client = get_client()
    results, _ = fetch_many(lambda gw: client.entry_picks(entry, gw), gws)
    return results


def available_gameweeks(events: list[dict]) -> list[dict]:
    """Gameweeks whose deadline has passed (others' teams are hidden before that)."""
    now = pd.Timestamp.now(tz="UTC")
    out = []
    for e in events:
        deadline = pd.to_datetime(e.get("deadline_time"), utc=True) if e.get("deadline_time") else None
        if e.get("finished") or e.get("is_current") or (deadline is not None and deadline <= now):
            out.append(e)
    return sorted(out, key=lambda e: e["id"])


def gameweek_status(event: dict) -> str:
    """'Final', 'Provisional' (finished, bonus not yet confirmed) or 'Live'."""
    if event.get("finished") and event.get("data_checked"):
        return "Final"
    if event.get("finished"):
        return "Provisional"
    return "Live"

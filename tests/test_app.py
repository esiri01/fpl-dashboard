"""Smoke tests: run the whole Streamlit script headlessly (no browser, no network)."""

from pathlib import Path

import pytest
import responses
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "fpl_dashboard.py")


@pytest.fixture(autouse=True)
def fresh_caches():
    import streamlit as st

    st.cache_data.clear()
    st.cache_resource.clear()
    yield


def test_all_tabs_render_on_sample_data(monkeypatch):
    sample = ROOT / "sample_data"
    if not sample.exists():
        pytest.skip("run scripts/make_sample_data.py first")
    monkeypatch.setenv("FPL_FIXTURES_DIR", str(sample))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error
    assert at.title[0].value == "Mech Peeps"
    assert len(at.tabs) == 3
    subheaders = [s.value for s in at.subheader]
    for expected in ("Gameweek 8 results", "Captaincy", "Points race", "Season stats",
                     "Points per gameweek", "Captain history", "Chips"):
        assert expected in subheaders


@responses.activate
def test_api_down_shows_friendly_error(monkeypatch):
    monkeypatch.delenv("FPL_FIXTURES_DIR", raising=False)
    responses.get("https://fantasy.premierleague.com/api/bootstrap-static/", status=500)
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.error and "Couldn't load data" in at.error[0].value

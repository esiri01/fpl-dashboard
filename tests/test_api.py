import json

import pytest
import responses

from fpl.api import FPLClient, FPLError, NotFound, fetch_many, fixture_name, make_session

BASE = "https://fantasy.premierleague.com/api"


def load(fixtures_dir, name):
    return json.loads((fixtures_dir / name).read_text())


@pytest.fixture
def client():
    # backoff=0 keeps retry tests fast
    return FPLClient(session=make_session(retries=3, backoff=0))


@responses.activate
def test_standings_pagination_merges_pages(client, fixtures_dir):
    url = f"{BASE}/leagues-classic/416802/standings/"
    responses.get(url, json=load(fixtures_dir, "standings_page1.json"),
                  match=[responses.matchers.query_param_matcher({"page_standings": "1"})])
    responses.get(url, json=load(fixtures_dir, "standings_page2.json"),
                  match=[responses.matchers.query_param_matcher({"page_standings": "2"})])
    league, managers = client.league_standings(416802)
    assert league["name"] == "Mech Peeps"
    assert league["start_event"] == 1
    assert [m["entry"] for m in managers] == [101, 102, 103]


@responses.activate
def test_new_league_falls_back_to_new_entries(client):
    responses.get(f"{BASE}/leagues-classic/9/standings/", json={
        "league": {"name": "Fresh"},
        "standings": {"has_next": False, "results": []},
        "new_entries": {"has_next": False, "results": [
            {"entry": 5, "entry_name": "Team", "player_first_name": "Ada", "player_last_name": "L"}]},
    })
    _, managers = client.league_standings(9)
    assert managers[0]["entry"] == 5 and managers[0]["player_name"] == "Ada L"


@responses.activate
def test_retries_on_429_then_succeeds(client):
    url = f"{BASE}/bootstrap-static/"
    responses.get(url, status=429)
    responses.get(url, json={"events": []})
    assert client.bootstrap() == {"events": []}
    assert len(responses.calls) == 2


@responses.activate
def test_sends_browser_user_agent(client):
    responses.get(f"{BASE}/bootstrap-static/", json={})
    client.bootstrap()
    assert "Mozilla" in responses.calls[0].request.headers["User-Agent"]


@responses.activate
def test_404_raises_not_found(client):
    responses.get(f"{BASE}/entry/1/history/", status=404)
    with pytest.raises(NotFound):
        client.entry_history(1)


@responses.activate
def test_server_error_raises_fpl_error_after_retries(client):
    responses.get(f"{BASE}/entry/1/history/", status=500)
    with pytest.raises(FPLError):
        client.entry_history(1)


@responses.activate
def test_one_bad_manager_is_reported_not_fatal(client):
    responses.get(f"{BASE}/entry/1/history/", json={"current": []})
    responses.get(f"{BASE}/entry/2/history/", status=404)
    results, failures = fetch_many(client.entry_history, [1, 2])
    assert list(results) == [1]
    assert list(failures) == [2]


def test_history_without_chips_parses(managers):
    from fpl import metrics

    s = metrics.build_season_frame(managers, {1: {"current": [{"event": 1, "points": 50}]}})
    assert s.iloc[0]["net_points"] == 50 and s.iloc[0]["hits"] == 0


def test_offline_fixtures_mode(tmp_path):
    (tmp_path / fixture_name("entry/7/history/")).write_text('{"current": []}')
    client = FPLClient(fixtures_dir=tmp_path)
    assert client.entry_history(7) == {"current": []}
    with pytest.raises(NotFound):
        client.entry_history(8)


def test_fixture_name():
    assert fixture_name("entry/1/event/4/picks/") == "entry__1__event__4__picks.json"
    assert fixture_name("leagues-classic/9/standings/", {"page_standings": 2}) == (
        "leagues-classic__9__standings__page_standings-2.json")

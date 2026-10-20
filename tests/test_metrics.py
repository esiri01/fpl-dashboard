import pandas as pd

from fpl import metrics


def test_competition_rank_ties_skip_next_place():
    ranks = metrics.competition_rank(pd.Series([78, 78, 71, 65]))
    assert ranks.tolist() == [1, 1, 3, 4]
    assert metrics.rank_labels(ranks).tolist() == ["1=", "1=", "3", "4"]


def test_podium_uses_distinct_scores(season):
    table = metrics.gameweek_table(season, 2)
    steps = metrics.podium(table)
    assert [s["score"] for s in steps] == [78, 71, 65]
    assert sorted(steps[0]["rows"]["manager"]) == ["Ada", "Bo"]


def test_net_points_subtract_hits(season):
    cy = season[(season["manager"] == "Cy") & (season["gw"] == 2)].iloc[0]
    assert (cy["points"], cy["hits"], cy["net_points"]) == (75, 4, 71)


def test_league_rank_and_movement(season):
    gw1 = season[season["gw"] == 1].set_index("manager")
    gw2 = season[season["gw"] == 2].set_index("manager")
    # GW1: Cy 70, Bo 60, Ada 50, Di 40. GW2 totals: Bo 138, Cy 141, Ada 128, Di 105.
    assert gw1["league_rank"].to_dict() == {"Ada": 3, "Bo": 2, "Cy": 1, "Di": 4}
    assert gw2["league_rank"].to_dict() == {"Ada": 3, "Bo": 2, "Cy": 1, "Di": 4}
    assert (gw2["movement"] == 0).all()
    assert (gw1["movement"] == 0).all()  # no previous week -> no movement


def test_movement_sign_climbing_is_positive(managers):
    histories = {
        1: metrics_history([(1, 10), (2, 100)]),
        2: metrics_history([(1, 50), (2, 0)]),
        3: metrics_history([(1, 40), (2, 0)]),
        4: metrics_history([(1, 30), (2, 0)]),
    }
    s = metrics.build_season_frame(managers, histories)
    ada = s[(s["manager"] == "Ada") & (s["gw"] == 2)].iloc[0]
    assert (ada["prev_league_rank"], ada["league_rank"], ada["movement"]) == (4, 1, 3)
    mv = metrics.movers(metrics.gameweek_table(s, 2))
    assert mv["climb"]["manager"].tolist() == ["Ada"]


def metrics_history(rows):
    from conftest import history

    return history([(gw, pts, 0) for gw, pts in rows])


def test_weekly_wins_count_ties_for_everyone(season):
    tally = metrics.wins_tally(season).set_index("manager")
    assert tally.loc["Ada", "wins"] == 1 and tally.loc["Bo", "wins"] == 1  # tied GW2
    assert tally.loc["Cy", "wins"] == 1  # GW1
    assert "Di" not in tally.index


def test_captain_return_uses_multiplier():
    picks = {
        1: {"active_chip": None, "picks": [
            {"element": 10, "multiplier": 2, "is_captain": True, "is_vice_captain": False},
            {"element": 11, "multiplier": 1, "is_captain": False, "is_vice_captain": True}]},
        2: {"active_chip": "3xc", "picks": [
            {"element": 10, "multiplier": 3, "is_captain": True, "is_vice_captain": False}]},
    }
    live = {"elements": [{"id": 10, "stats": {"total_points": 9, "minutes": 90}},
                         {"id": 11, "stats": {"total_points": 4, "minutes": 90}}]}
    caps = metrics.captain_frame(picks, live, {10: "Haaland", 11: "Salah"}, gw_finished=True)
    assert caps.set_index("entry")["captain_return"].to_dict() == {1: 18, 2: 27}
    summary = metrics.captain_summary(caps)
    assert summary.iloc[0][["captain", "managers", "doubled"]].tolist() == ["Haaland", 2, 18]


def test_vice_captain_scores_when_captain_blanks_in_finished_gw():
    picks = {1: {"picks": [
        {"element": 10, "multiplier": 2, "is_captain": True, "is_vice_captain": False},
        {"element": 11, "multiplier": 1, "is_captain": False, "is_vice_captain": True}]}}
    live = {"elements": [{"id": 10, "stats": {"total_points": 0, "minutes": 0}},
                         {"id": 11, "stats": {"total_points": 6, "minutes": 90}}]}
    cap = metrics.captain_frame(picks, live, {10: "Haaland", 11: "Salah"}, gw_finished=True).iloc[0]
    assert cap["used_vice"] and cap["scored_by"] == "Salah" and cap["captain_return"] == 12
    live_cap = metrics.captain_frame(picks, live, {}, gw_finished=False).iloc[0]
    assert not live_cap["used_vice"]  # still live: captain might yet play


def test_season_stats(season):
    stats = metrics.season_stats(season).set_index("manager")
    assert stats.loc["Cy", "rank_label"] == "1"
    assert stats.loc["Cy", "hits"] == 4
    assert stats.loc["Bo", "behind"] == 3
    assert stats.loc["Bo", "chips"] == "Bench Boost (GW2)"
    assert stats.loc["Bo", "bench"] == 9


def test_league_start_event_excludes_earlier_gameweeks(managers, season):
    from conftest import history

    hist = {e: history([(1, 50, 0), (2, 60 + e, 0)]) for e in managers["entry"]}
    s = metrics.build_season_frame(managers, hist, start_event=2)
    assert s["gw"].unique().tolist() == [2]
    assert s.set_index("manager")["league_points"].to_dict() == {"Ada": 61, "Bo": 62, "Cy": 63, "Di": 64}


def test_empty_inputs_do_not_crash(managers):
    s = metrics.build_season_frame(managers, {})
    assert s.empty
    assert metrics.gameweek_table(s, 1).empty
    assert metrics.podium(metrics.gameweek_table(s, 1)) == []
    assert metrics.season_stats(s).empty
    assert metrics.captain_frame({}, None, {}, False).empty


def test_ordinal():
    assert [metrics.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd"]

"""Altair chart builders (Altair ships with Streamlit, so no extra dependency)."""

from __future__ import annotations

import altair as alt
import pandas as pd

from fpl.config import ACCENT, HIGHLIGHT_COLORS, INK, MUTED_LINE

AXIS = {"labelColor": "#5B6660", "titleColor": "#5B6660", "gridColor": "#ECEEE9", "domain": False}


def _color_scale(highlight: list[str]) -> alt.Scale:
    return alt.Scale(
        domain=highlight + ["Everyone else"],
        range=HIGHLIGHT_COLORS[: len(highlight)] + [MUTED_LINE],
    )


def _with_groups(df: pd.DataFrame, highlight: list[str]) -> pd.DataFrame:
    df = df.copy()
    df["group"] = df["manager"].where(df["manager"].isin(highlight), "Everyone else")
    df["is_highlight"] = df["manager"].isin(highlight)
    return df


def points_race(gaps: pd.DataFrame, highlight: list[str]) -> alt.LayerChart:
    """Points behind the leader per gameweek; top managers coloured, hover isolates a line."""
    df = _with_groups(gaps, highlight)
    hover = alt.selection_point(fields=["manager"], on="pointerover", nearest=True, empty=True)
    max_gap = max(int(df["gap"].max()), 10)
    base = alt.Chart(df).encode(
        x=alt.X("gw:O", title="Gameweek", axis=alt.Axis(labelAngle=0, **AXIS)),
        y=alt.Y(
            "gap:Q",
            title="Points behind leader",
            scale=alt.Scale(domain=[max_gap, 0]),
            axis=alt.Axis(**AXIS),
        ),
        detail="manager:N",
    )
    lines = base.mark_line(point=False, interpolate="linear").encode(
        color=alt.Color("group:N", scale=_color_scale(highlight), legend=alt.Legend(title=None, orient="top")),
        strokeWidth=alt.condition("datum.is_highlight", alt.value(3), alt.value(1.5)),
        opacity=alt.condition(hover, alt.value(1), alt.value(0.25)),
    )
    points = base.mark_circle(size=60, opacity=0).encode(
        tooltip=[
            alt.Tooltip("manager:N", title="Manager"),
            alt.Tooltip("gw:O", title="GW"),
            alt.Tooltip("league_points:Q", title="Total"),
            alt.Tooltip("gap:Q", title="Behind leader"),
            alt.Tooltip("league_rank:Q", title="League rank"),
        ]
    ).add_params(hover)
    return (lines + points).properties(height=340)


def league_position(season: pd.DataFrame, highlight: list[str]) -> alt.LayerChart:
    """Bump chart of league rank by gameweek (1st at the top)."""
    df = _with_groups(season[["gw", "manager", "league_rank", "league_points"]], highlight)
    n = int(df["league_rank"].max()) if not df.empty else 1
    hover = alt.selection_point(fields=["manager"], on="pointerover", nearest=True, empty=True)
    base = alt.Chart(df).encode(
        x=alt.X("gw:O", title="Gameweek", axis=alt.Axis(labelAngle=0, **AXIS)),
        y=alt.Y(
            "league_rank:Q",
            title="League position",
            scale=alt.Scale(domain=[n + 0.5, 0.5], nice=False),
            axis=alt.Axis(values=list(range(1, n + 1)), format="d", **AXIS),
        ),
        detail="manager:N",
    )
    lines = base.mark_line(interpolate="linear").encode(
        color=alt.Color("group:N", scale=_color_scale(highlight), legend=None),
        strokeWidth=alt.condition("datum.is_highlight", alt.value(3), alt.value(1.5)),
        opacity=alt.condition(hover, alt.value(1), alt.value(0.25)),
    )
    dots = base.mark_circle(size=50).encode(
        color=alt.Color("group:N", scale=_color_scale(highlight), legend=None),
        opacity=alt.condition(hover, alt.value(1), alt.value(0.25)),
        tooltip=[
            alt.Tooltip("manager:N", title="Manager"),
            alt.Tooltip("gw:O", title="GW"),
            alt.Tooltip("league_rank:Q", title="Position"),
            alt.Tooltip("league_points:Q", title="Total"),
        ],
    ).add_params(hover)
    return (lines + dots).properties(height=340)


def wins_bar(tally: pd.DataFrame) -> alt.Chart:
    """Horizontal bars: gameweeks won per manager."""
    return (
        alt.Chart(tally)
        .mark_bar(color=ACCENT, cornerRadiusEnd=4, height=18)
        .encode(
            x=alt.X("wins:Q", title="Gameweeks won", axis=alt.Axis(tickMinStep=1, format="d", **AXIS)),
            y=alt.Y("manager:N", sort="-x", title=None, axis=alt.Axis(**AXIS)),
            tooltip=[alt.Tooltip("manager:N", title="Manager"), alt.Tooltip("wins:Q", title="Wins"),
                     alt.Tooltip("gws:N", title="Gameweeks")],
        )
        .properties(height=max(120, 34 * len(tally)))
    )


def manager_points(history: pd.DataFrame, averages: pd.DataFrame) -> alt.LayerChart:
    """One manager's net points per gameweek as bars, league average as a dashed line."""
    df = history.merge(averages, on="gw", how="left")
    x = alt.X("gw:O", title="Gameweek", axis=alt.Axis(labelAngle=0, **AXIS))
    bars = alt.Chart(df).mark_bar(color=ACCENT, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=x,
        y=alt.Y("net_points:Q", title="Net points", axis=alt.Axis(**AXIS)),
        tooltip=[
            alt.Tooltip("gw:O", title="GW"),
            alt.Tooltip("points:Q", title="Points"),
            alt.Tooltip("hits:Q", title="Hits"),
            alt.Tooltip("net_points:Q", title="Net"),
            alt.Tooltip("league_avg:Q", title="League avg", format=".1f"),
        ],
    )
    labels = alt.Chart(df).mark_text(dy=-8, color=INK, fontWeight=600).encode(
        x=x, y="net_points:Q", text="net_points:Q"
    )
    avg = alt.Chart(df).mark_line(color=INK, strokeDash=[6, 4], point=alt.OverlayMarkDef(
        filled=True, fill="white", stroke=INK, size=40)).encode(x=x, y="league_avg:Q")
    return (bars + labels + avg).properties(height=300)


def manager_rank(history: pd.DataFrame, n_managers: int) -> alt.Chart:
    """One manager's league position over time."""
    return (
        alt.Chart(history)
        .mark_line(color=ACCENT, strokeWidth=3, point=alt.OverlayMarkDef(color=ACCENT, size=60))
        .encode(
            x=alt.X("gw:O", title="Gameweek", axis=alt.Axis(labelAngle=0, **AXIS)),
            y=alt.Y(
                "league_rank:Q",
                title="League position",
                scale=alt.Scale(domain=[n_managers + 0.5, 0.5], nice=False),
                axis=alt.Axis(values=list(range(1, n_managers + 1)), format="d", **AXIS),
            ),
            tooltip=[alt.Tooltip("gw:O", title="GW"), alt.Tooltip("league_rank:Q", title="Position")],
        )
        .properties(height=300)
    )

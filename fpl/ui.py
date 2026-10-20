"""Small presentation helpers shared by the views (a little CSS for cards, nothing heavy)."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

import pandas as pd
import streamlit as st

CSS = """
<style>
.block-container {padding-top: 3.5rem; max-width: 1400px;}
.pf-eyebrow {font-size: .8rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: #5B6660; margin-bottom: -.4rem;}
.pf-chips {display: flex; gap: .5rem; flex-wrap: wrap; justify-content: flex-end; padding-top: 1.6rem;}
.pf-chip {padding: .3rem .8rem; border-radius: 999px; background: #fff; border: 1px solid #E1E4DE; font-size: .85rem; font-weight: 500;}
.pf-card {background: #fff; border: 1px solid #E1E4DE; border-radius: 12px; padding: 1rem 1.2rem; height: 100%; box-sizing: border-box;}
.pf-card.gold {border-top: 6px solid #C99A2E;}
.pf-card.silver {border-top: 6px solid #9AA3A0;}
.pf-card.bronze {border-top: 6px solid #A86A3D;}
.pf-label {font-size: .78rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: #4F5955;}
.pf-label.gold {color: #7A5410;}
.pf-label.bronze {color: #7E4A26;}
.pf-name {font-size: 1.3rem; font-weight: 600; margin-top: .3rem; line-height: 1.25;}
.pf-sub {font-size: .9rem; color: #5B6660;}
.pf-big {font-size: 2.3rem; font-weight: 700; line-height: 1.1; margin-top: .4rem; font-variant-numeric: tabular-nums;}
.pf-up {color: #1F7A4D; font-weight: 600;}
.pf-down {color: #A63B28; font-weight: 600;}
.pf-callout {border-radius: 10px; padding: .75rem .9rem; height: 100%; box-sizing: border-box;}
.pf-callout.good {background: #E3F1E8; color: #2F4A3A;}
.pf-callout.bad {background: #F8E6DF; color: #5A3226;}
.pf-chipbox {border: 1px dashed #B9C0BA; border-radius: 10px; padding: .7rem .9rem; margin-bottom: .6rem;}
.pf-chipbox.used {border-style: solid; background: #F4F5F1;}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def e(text) -> str:
    """HTML-escape anything shown inside custom markup (manager/team names are user-chosen)."""
    return escape(str(text))


def names(rows: pd.DataFrame, col: str = "manager") -> str:
    return ", ".join(rows[col].astype(str))


def movement_text(m: int) -> str:
    if m > 0:
        return f"▲ {m}"
    if m < 0:
        return f"▼ {-m}"
    return "–"


@dataclass
class Context:
    """Everything a view needs, loaded once in the main script."""

    league_id: str
    league: dict
    season: pd.DataFrame  # full season, all gameweeks
    gw: int
    event: dict
    status: str
    players: dict[int, str]
    total_players: int | None
    n_managers: int
    events: list[dict] = field(default_factory=list)
    chip_rules: list[dict] = field(default_factory=list)

    @property
    def finished(self) -> bool:
        return bool(self.event.get("finished"))

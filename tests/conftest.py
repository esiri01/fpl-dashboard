import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIXTURES = Path(__file__).parent / "fixtures"


def history(rows, chips=()):
    """Build an /entry/{id}/history/ payload from (gw, points, hits[, bench]) tuples."""
    current, total = [], 0
    for r in rows:
        gw, pts, hits = r[:3]
        bench = r[3] if len(r) > 3 else 0
        total += pts - hits
        current.append({
            "event": gw, "points": pts, "total_points": total, "overall_rank": 100_000,
            "event_transfers": hits // 4, "event_transfers_cost": hits, "points_on_bench": bench,
        })
    return {"current": current, "past": [], "chips": [{"name": n, "event": e} for n, e in chips]}


@pytest.fixture
def fixtures_dir():
    return FIXTURES


@pytest.fixture
def managers():
    return pd.DataFrame({
        "entry": [1, 2, 3, 4],
        "manager": ["Ada", "Bo", "Cy", "Di"],
        "team": ["A FC", "B FC", "C FC", "D FC"],
    })


@pytest.fixture
def season(managers):
    """Two gameweeks. GW2 scores 78, 78, 71, 65 (tie at the top); Cy takes a hit."""
    from fpl import metrics

    histories = {
        1: history([(1, 50, 0), (2, 78, 0)]),
        2: history([(1, 60, 0), (2, 78, 0, 9)], chips=[("bboost", 2)]),
        3: history([(1, 70, 0), (2, 75, 4)]),
        4: history([(1, 40, 0), (2, 65, 0)]),
    }
    return metrics.build_season_frame(managers, histories)

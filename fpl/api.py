"""Thin client for the public (unofficial) FPL API.

No Streamlit in here, so it can be unit-tested with mocked HTTP.
Caching lives in ``fpl.data``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from fpl import config

log = logging.getLogger(__name__)


class FPLError(Exception):
    """Any failure talking to the FPL API."""


class NotFound(FPLError):
    """The FPL API returned 404 (bad league / entry ID, or no data yet)."""


def make_session(retries: int = 3, backoff: float = 0.5) -> requests.Session:
    """Session with a browser-like User-Agent and retries on 429/5xx."""
    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT, "Accept": "application/json"})
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=config.MAX_WORKERS * 2)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fixture_name(path: str, params: dict[str, Any] | None = None) -> str:
    """File name used for a saved response in offline mode.

    ``entry/123/event/4/picks/`` -> ``entry__123__event__4__picks.json``
    """
    name = path.strip("/").replace("/", "__")
    if params:
        name += "__" + "__".join(f"{k}-{v}" for k, v in sorted(params.items()))
    return f"{name}.json"


class FPLClient:
    """All endpoints the dashboard uses."""

    def __init__(
        self,
        base_url: str = config.BASE_URL,
        session: requests.Session | None = None,
        timeout: float = config.TIMEOUT_SECONDS,
        fixtures_dir: str | Path | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or make_session()
        self.timeout = timeout
        self.fixtures_dir = Path(fixtures_dir) if fixtures_dir else None

    # ---------- transport ----------
    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        if self.fixtures_dir is not None:
            file = self.fixtures_dir / fixture_name(path, params)
            if not file.exists():
                raise NotFound(f"No saved response for {path} ({file.name})")
            return json.loads(file.read_text())

        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:  # timeouts, DNS, connection resets
            raise FPLError(f"Could not reach the FPL API ({exc.__class__.__name__}).") from exc
        if resp.status_code == 404:
            raise NotFound(f"Not found: {path}")
        if resp.status_code == 503:
            raise FPLError("The FPL API is updating (503). Try again in a few minutes.")
        if not resp.ok:
            raise FPLError(f"FPL API error {resp.status_code} for {path}")
        try:
            return resp.json()
        except ValueError as exc:
            raise FPLError(f"FPL API returned something that isn't JSON for {path}") from exc

    # ---------- endpoints ----------
    def bootstrap(self) -> dict:
        """Gameweeks (events), players (elements), teams, total_players."""
        return self._get("bootstrap-static/")

    def league_standings(self, league_id: str | int) -> tuple[dict, list[dict]]:
        """League info (``name``, ``start_event``) and every manager, following pagination.

        Before the league's first gameweek is scored, ``standings.results`` is empty and
        managers appear under ``new_entries`` instead; those are returned in the same shape.
        """
        managers: list[dict] = []
        league: dict = {"id": league_id, "name": f"League {league_id}", "start_event": 1}
        page = 1
        while page <= config.MAX_STANDINGS_PAGES:
            data = self._get(
                f"leagues-classic/{league_id}/standings/", {"page_standings": page}
            )
            info = data.get("league") or {}
            league["name"] = info.get("name") or league["name"]
            league["start_event"] = info.get("start_event") or league["start_event"]
            standings = data.get("standings") or {}
            managers.extend(standings.get("results") or [])
            if not standings.get("has_next"):
                break
            page += 1

        if not managers:
            for e in (data.get("new_entries") or {}).get("results") or []:
                managers.append(
                    {
                        "entry": e.get("entry"),
                        "entry_name": e.get("entry_name"),
                        "player_name": " ".join(
                            p for p in (e.get("player_first_name"), e.get("player_last_name")) if p
                        ),
                        "rank": None,
                        "last_rank": None,
                        "total": 0,
                    }
                )
        return league, managers

    def entry_history(self, entry_id: int) -> dict:
        """Every gameweek this season for one manager (+ chips used)."""
        return self._get(f"entry/{entry_id}/history/")

    def entry_picks(self, entry_id: int, gw: int) -> dict:
        """One manager's squad for one gameweek (captain, chip, multipliers)."""
        return self._get(f"entry/{entry_id}/event/{gw}/picks/")

    def event_live(self, gw: int) -> dict:
        """Live/final points for every player in a gameweek."""
        return self._get(f"event/{gw}/live/")


def fetch_many(
    func: Callable[[Any], Any],
    keys: Iterable[Any],
    max_workers: int = config.MAX_WORKERS,
) -> tuple[dict[Any, Any], dict[Any, str]]:
    """Run ``func(key)`` for each key in a bounded thread pool.

    Returns ``(results, failures)``; one bad key never sinks the rest.
    """
    keys = list(keys)
    results: dict[Any, Any] = {}
    failures: dict[Any, str] = {}
    if not keys:
        return results, failures
    with ThreadPoolExecutor(max_workers=min(max_workers, len(keys))) as pool:
        futures = {pool.submit(func, k): k for k in keys}
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                results[key] = fut.result()
            except Exception as exc:  # noqa: BLE001 - reported to the user, not swallowed
                log.warning("Fetch failed for %s: %s", key, exc)
                failures[key] = str(exc)
    return results, failures

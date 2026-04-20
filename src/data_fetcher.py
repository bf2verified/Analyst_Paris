"""Récupère statistiques d'équipes et historiques depuis des APIs football publiques."""
import os
import time
import json
from pathlib import Path
from typing import Optional, Dict, Tuple
import requests

CACHE_TTL = 60 * 30  # 30 minutes

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
API_FOOTBALL_BASE = "https://v3.football.api-sports.io"

# Cache: essaie le disque, sinon mémoire (filesystems éphémères: Fly, Railway, Vercel).
_CACHE_DIR: Optional[Path]
try:
    _dir = os.getenv("CACHE_DIR") or str(Path(__file__).resolve().parent.parent / "cache")
    _CACHE_DIR = Path(_dir)
    _CACHE_DIR.mkdir(exist_ok=True, parents=True)
    (_CACHE_DIR / ".probe").write_text("ok")
    (_CACHE_DIR / ".probe").unlink()
except Exception:
    _CACHE_DIR = None

_MEM_CACHE: Dict[str, Tuple[float, dict]] = {}


def _cached_get(key: str, fetch):
    now = time.time()
    if _CACHE_DIR is not None:
        safe = "".join(c if c.isalnum() else "_" for c in key)
        path = _CACHE_DIR / f"{safe}.json"
        if path.exists() and now - path.stat().st_mtime < CACHE_TTL:
            return json.loads(path.read_text())
        data = fetch()
        try:
            path.write_text(json.dumps(data))
        except OSError:
            pass
        return data
    cached = _MEM_CACHE.get(key)
    if cached and now - cached[0] < CACHE_TTL:
        return cached[1]
    data = fetch()
    _MEM_CACHE[key] = (now, data)
    return data


class FootballDataClient:
    """Client pour football-data.org (gratuit, limité aux 5 grands championnats)."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("FOOTBALL_DATA_API_KEY", "")
        self.headers = {"X-Auth-Token": self.api_key} if self.api_key else {}

    def _get(self, path: str, params: dict | None = None):
        url = f"{FOOTBALL_DATA_BASE}{path}"
        r = requests.get(url, headers=self.headers, params=params or {}, timeout=15)
        r.raise_for_status()
        return r.json()

    def competitions(self):
        return _cached_get("fd_competitions", lambda: self._get("/competitions"))

    def teams(self, competition_code: str):
        return _cached_get(
            f"fd_teams_{competition_code}",
            lambda: self._get(f"/competitions/{competition_code}/teams"),
        )

    def team_matches(self, team_id: int, limit: int = 20):
        return _cached_get(
            f"fd_matches_{team_id}_{limit}",
            lambda: self._get(f"/teams/{team_id}/matches", {"limit": limit, "status": "FINISHED"}),
        )

    def head_to_head(self, match_id: int):
        return _cached_get(
            f"fd_h2h_{match_id}",
            lambda: self._get(f"/matches/{match_id}/head2head", {"limit": 10}),
        )

    def upcoming_matches(self, competition_code: str):
        return _cached_get(
            f"fd_upcoming_{competition_code}",
            lambda: self._get(
                f"/competitions/{competition_code}/matches", {"status": "SCHEDULED"}
            ),
        )


class ApiFootballClient:
    """Client pour api-football.com (freemium, fournit corners, cartons, tirs...)."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("API_FOOTBALL_KEY", "")
        self.headers = {"x-apisports-key": self.api_key} if self.api_key else {}

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, params: dict | None = None):
        if not self.enabled:
            return None
        url = f"{API_FOOTBALL_BASE}{path}"
        r = requests.get(url, headers=self.headers, params=params or {}, timeout=15)
        r.raise_for_status()
        return r.json()

    def team_statistics(self, team_id: int, league_id: int, season: int):
        key = f"af_teamstats_{team_id}_{league_id}_{season}"
        return _cached_get(
            key,
            lambda: self._get(
                "/teams/statistics",
                {"team": team_id, "league": league_id, "season": season},
            ),
        )

    def fixture_statistics(self, fixture_id: int):
        return _cached_get(
            f"af_fixstats_{fixture_id}",
            lambda: self._get("/fixtures/statistics", {"fixture": fixture_id}),
        )

    def last_fixtures(self, team_id: int, last: int = 10):
        return _cached_get(
            f"af_last_{team_id}_{last}",
            lambda: self._get("/fixtures", {"team": team_id, "last": last}),
        )


def build_match_dossier(home_team: str, away_team: str, competition: str = "PL") -> dict:
    """Assemble un dossier complet pour un match donné à partir des APIs disponibles."""
    fd = FootballDataClient()
    af = ApiFootballClient()

    dossier = {
        "home": home_team,
        "away": away_team,
        "competition": competition,
        "sources": [],
        "home_stats": {},
        "away_stats": {},
        "h2h": [],
        "warnings": [],
    }

    if not fd.api_key:
        dossier["warnings"].append(
            "FOOTBALL_DATA_API_KEY manquant — données limitées."
        )
        return dossier

    try:
        teams_data = fd.teams(competition)
        teams = {t["name"].lower(): t for t in teams_data.get("teams", [])}
        home_entry = teams.get(home_team.lower())
        away_entry = teams.get(away_team.lower())

        if home_entry:
            home_matches = fd.team_matches(home_entry["id"])
            dossier["home_stats"] = _summarise_matches(home_matches, home_entry["id"])
            dossier["sources"].append("football-data.org")
        if away_entry:
            away_matches = fd.team_matches(away_entry["id"])
            dossier["away_stats"] = _summarise_matches(away_matches, away_entry["id"])
    except requests.RequestException as exc:
        dossier["warnings"].append(f"football-data.org: {exc}")

    if af.enabled:
        dossier["sources"].append("api-football.com")
        dossier["warnings"].append(
            "Pour corners/cartons détaillés, mappez vos IDs d'équipe api-football."
        )

    return dossier


def _summarise_matches(matches_payload: dict, team_id: int) -> dict:
    matches = matches_payload.get("matches", [])
    goals_for = goals_against = 0
    wins = draws = losses = 0
    btts = over25 = clean_sheets = 0
    played = len(matches)
    goal_minutes = []

    for m in matches:
        home = m["homeTeam"]["id"] == team_id
        score = m.get("score", {}).get("fullTime", {}) or {}
        gf = score.get("home" if home else "away") or 0
        ga = score.get("away" if home else "home") or 0
        goals_for += gf
        goals_against += ga
        if gf > ga:
            wins += 1
        elif gf == ga:
            draws += 1
        else:
            losses += 1
        if gf > 0 and ga > 0:
            btts += 1
        if gf + ga > 2:
            over25 += 1
        if ga == 0:
            clean_sheets += 1

    return {
        "played": played,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "avg_goals_for": round(goals_for / played, 2) if played else 0,
        "avg_goals_against": round(goals_against / played, 2) if played else 0,
        "btts_rate": round(btts / played, 3) if played else 0,
        "over25_rate": round(over25 / played, 3) if played else 0,
        "clean_sheet_rate": round(clean_sheets / played, 3) if played else 0,
        "recent_form": [
            _form_letter(m, team_id) for m in matches[:5]
        ],
    }


def _form_letter(match: dict, team_id: int) -> str:
    home = match["homeTeam"]["id"] == team_id
    score = match.get("score", {}).get("fullTime", {}) or {}
    gf = score.get("home" if home else "away") or 0
    ga = score.get("away" if home else "home") or 0
    if gf > ga:
        return "W"
    if gf == ga:
        return "D"
    return "L"

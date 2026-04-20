"""Analyse statistique des marchés de paris avec modèle de Poisson."""
from math import exp, factorial
from typing import Dict, List, Tuple

LEAGUE_AVG_GOALS_HOME = 1.52
LEAGUE_AVG_GOALS_AWAY = 1.18


def _poisson(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * exp(-lam) / factorial(k)


def expected_goals(home_stats: dict, away_stats: dict) -> Tuple[float, float]:
    """Estime les xG domicile/extérieur via les moyennes d'attaque/défense."""
    if not home_stats or not away_stats:
        return LEAGUE_AVG_GOALS_HOME, LEAGUE_AVG_GOALS_AWAY

    home_attack = home_stats.get("avg_goals_for", LEAGUE_AVG_GOALS_HOME) / LEAGUE_AVG_GOALS_HOME
    away_defense = away_stats.get("avg_goals_against", LEAGUE_AVG_GOALS_AWAY) / LEAGUE_AVG_GOALS_AWAY
    away_attack = away_stats.get("avg_goals_for", LEAGUE_AVG_GOALS_AWAY) / LEAGUE_AVG_GOALS_AWAY
    home_defense = home_stats.get("avg_goals_against", LEAGUE_AVG_GOALS_HOME) / LEAGUE_AVG_GOALS_HOME

    lam_home = max(0.1, home_attack * away_defense * LEAGUE_AVG_GOALS_HOME)
    lam_away = max(0.1, away_attack * home_defense * LEAGUE_AVG_GOALS_AWAY)
    return round(lam_home, 2), round(lam_away, 2)


def score_matrix(lam_h: float, lam_a: float, max_goals: int = 6) -> List[List[float]]:
    return [
        [_poisson(h, lam_h) * _poisson(a, lam_a) for a in range(max_goals + 1)]
        for h in range(max_goals + 1)
    ]


def market_probabilities(lam_h: float, lam_a: float) -> Dict[str, float]:
    """Calcule les probabilités pour tous les marchés dérivables de Poisson."""
    matrix = score_matrix(lam_h, lam_a)
    p_home = p_draw = p_away = 0.0
    p_btts = p_over15 = p_over25 = p_over35 = p_under25 = 0.0
    p_exact: Dict[str, float] = {}

    for h, row in enumerate(matrix):
        for a, p in enumerate(row):
            if h > a:
                p_home += p
            elif h == a:
                p_draw += p
            else:
                p_away += p
            if h > 0 and a > 0:
                p_btts += p
            total = h + a
            if total > 1:
                p_over15 += p
            if total > 2:
                p_over25 += p
            if total > 3:
                p_over35 += p
            if total < 3:
                p_under25 += p
            p_exact[f"{h}-{a}"] = p

    top_scores = sorted(p_exact.items(), key=lambda x: x[1], reverse=True)[:6]

    return {
        "1X2": {
            "home": round(p_home, 3),
            "draw": round(p_draw, 3),
            "away": round(p_away, 3),
        },
        "double_chance": {
            "1X": round(p_home + p_draw, 3),
            "12": round(p_home + p_away, 3),
            "X2": round(p_draw + p_away, 3),
        },
        "btts": {"yes": round(p_btts, 3), "no": round(1 - p_btts, 3)},
        "over_under": {
            "over_1.5": round(p_over15, 3),
            "over_2.5": round(p_over25, 3),
            "over_3.5": round(p_over35, 3),
            "under_2.5": round(p_under25, 3),
        },
        "top_exact_scores": [
            {"score": s, "probability": round(p, 3)} for s, p in top_scores
        ],
        "european_handicap": _handicap(matrix),
    }


def _handicap(matrix: List[List[float]]) -> Dict[str, float]:
    """Handicap européen -1 / +1 pour le domicile."""
    home_minus1_win = home_minus1_draw = home_minus1_loss = 0.0
    for h, row in enumerate(matrix):
        for a, p in enumerate(row):
            diff = h - a - 1
            if diff > 0:
                home_minus1_win += p
            elif diff == 0:
                home_minus1_draw += p
            else:
                home_minus1_loss += p
    return {
        "home_-1": round(home_minus1_win, 3),
        "home_-1_draw": round(home_minus1_draw, 3),
        "away_+1": round(home_minus1_loss, 3),
    }


def corners_expectation(home_stats: dict, away_stats: dict) -> Dict[str, float]:
    """Estime les corners attendus (total + par équipe). Moyenne ligue ~10.5 par match."""
    base = 10.5
    attack_factor = 1.0
    if home_stats.get("avg_goals_for") and away_stats.get("avg_goals_for"):
        goals = home_stats["avg_goals_for"] + away_stats["avg_goals_for"]
        attack_factor = goals / (LEAGUE_AVG_GOALS_HOME + LEAGUE_AVG_GOALS_AWAY)
    expected_total = round(base * attack_factor, 2)

    # Répartition: équipe à domicile ~55% des corners (avantage du terrain).
    home_share = 0.55
    if home_stats.get("avg_goals_for") and away_stats.get("avg_goals_for"):
        h = home_stats["avg_goals_for"]
        a = away_stats["avg_goals_for"]
        if h + a > 0:
            home_share = max(0.35, min(0.70, 0.5 + 0.1 * (h - a) / max(h + a, 0.1)))
    expected_home = round(expected_total * home_share, 2)
    expected_away = round(expected_total * (1 - home_share), 2)

    return {
        "expected_total_corners": expected_total,
        "expected_home_corners": expected_home,
        "expected_away_corners": expected_away,
        "prob_over_8.5": round(_poisson_over(expected_total, 9), 3),
        "prob_over_9.5": round(_poisson_over(expected_total, 10), 3),
        "prob_over_10.5": round(_poisson_over(expected_total, 11), 3),
        "prob_home_over_3.5": round(_poisson_over(expected_home, 4), 3),
        "prob_home_over_4.5": round(_poisson_over(expected_home, 5), 3),
        "prob_home_over_5.5": round(_poisson_over(expected_home, 6), 3),
        "prob_away_over_3.5": round(_poisson_over(expected_away, 4), 3),
        "prob_away_over_4.5": round(_poisson_over(expected_away, 5), 3),
        "prob_away_over_5.5": round(_poisson_over(expected_away, 6), 3),
        "note": "Estimation basée sur l'agressivité offensive + avantage du terrain (~55/45). Utilisez API-Football pour corners réels.",
    }


def cards_expectation(home_stats: dict, away_stats: dict) -> Dict[str, float]:
    """Estime les cartons attendus. Moyenne ligue ~4.2 par match."""
    base = 4.2
    return {
        "expected_total_cards": base,
        "prob_over_3.5": round(_poisson_over(base, 4), 3),
        "prob_over_4.5": round(_poisson_over(base, 5), 3),
        "prob_over_5.5": round(_poisson_over(base, 6), 3),
        "note": "Moyenne statique; agressivité de l'arbitre à croiser pour plus de précision.",
    }


def _poisson_over(lam: float, threshold: int) -> float:
    total = sum(_poisson(k, lam) for k in range(threshold))
    return max(0.0, 1 - total)


def goal_minutes_distribution(lam_h: float, lam_a: float) -> Dict[str, float]:
    """Distribution approximative des minutes du premier but et des intervalles."""
    lam_total = lam_h + lam_a
    if lam_total <= 0:
        return {"prob_goal_0_15": 0, "prob_goal_16_30": 0, "prob_goal_31_45": 0,
                "prob_goal_46_60": 0, "prob_goal_61_75": 0, "prob_goal_76_90": 0}
    per_interval = lam_total / 6
    prob_goal_in_interval = round(1 - exp(-per_interval), 3)
    return {
        "prob_goal_0_15": prob_goal_in_interval,
        "prob_goal_16_30": prob_goal_in_interval,
        "prob_goal_31_45": prob_goal_in_interval,
        "prob_goal_46_60": prob_goal_in_interval,
        "prob_goal_61_75": prob_goal_in_interval,
        "prob_goal_76_90": prob_goal_in_interval,
        "expected_total_minutes_with_goal": round(6 * prob_goal_in_interval, 2),
    }


def consecutive_goals(lam_h: float, lam_a: float) -> Dict[str, float]:
    """But affilé: probabilité qu'une équipe marque 2+ buts de suite sans réponse adverse.

    Approximation: P(home marque 2+) * P(away marque 0) + symétrique.
    """
    p_home_0 = _poisson(0, lam_h)
    p_home_1 = _poisson(1, lam_h)
    p_home_2plus = 1 - p_home_0 - p_home_1
    p_away_0 = _poisson(0, lam_a)
    p_away_1 = _poisson(1, lam_a)
    p_away_2plus = 1 - p_away_0 - p_away_1
    return {
        "home_2_consecutive": round(p_home_2plus * p_away_0, 3),
        "away_2_consecutive": round(p_away_2plus * p_home_0, 3),
        "any_team_2_consecutive": round(
            p_home_2plus * p_away_0 + p_away_2plus * p_home_0, 3
        ),
    }


def goal_from_shot_estimate(home_stats: dict, away_stats: dict) -> Dict[str, float]:
    """Probabilité qu'un but vienne d'un tir (toujours vrai en football ~95%).

    Ce marché 1xBet se décline en «but marqué par tir cadré / tête / penalty».
    Sans données par-événement, on fournit des priors raisonnables basés sur stats UEFA.
    """
    return {
        "prob_any_goal_from_shot": 0.95,
        "prob_any_goal_from_header": 0.18,
        "prob_any_goal_from_penalty": 0.11,
        "prob_any_goal_from_free_kick": 0.04,
        "note": "Priors basés sur moyennes UEFA; pour précision, utilisez API-Football fixtures/statistics.",
    }


def analyse_match(home_stats: dict, away_stats: dict) -> dict:
    """Pipeline complet d'analyse d'un match."""
    lam_h, lam_a = expected_goals(home_stats, away_stats)
    return {
        "expected_goals": {"home": lam_h, "away": lam_a, "total": round(lam_h + lam_a, 2)},
        "markets": market_probabilities(lam_h, lam_a),
        "corners": corners_expectation(home_stats, away_stats),
        "cards": cards_expectation(home_stats, away_stats),
        "goal_minutes": goal_minutes_distribution(lam_h, lam_a),
        "consecutive_goals": consecutive_goals(lam_h, lam_a),
        "goal_origin": goal_from_shot_estimate(home_stats, away_stats),
    }

"""Analyse statistique des marchés de paris avec modèle de Poisson."""
import random
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
    # Si api-football nous donne les vraies moyennes de corners, on les utilise.
    if "avg_corners" in home_stats and "avg_corners" in away_stats:
        expected_home = round(home_stats["avg_corners"], 2)
        expected_away = round(away_stats["avg_corners"], 2)
        expected_total = round(expected_home + expected_away, 2)
        note_suffix = " — source: api-football (moyennes réelles)"
    else:
        base = 10.5
        attack_factor = 1.0
        if home_stats.get("avg_goals_for") and away_stats.get("avg_goals_for"):
            goals = home_stats["avg_goals_for"] + away_stats["avg_goals_for"]
            attack_factor = goals / (LEAGUE_AVG_GOALS_HOME + LEAGUE_AVG_GOALS_AWAY)
        expected_total = round(base * attack_factor, 2)

        home_share = 0.55
        if home_stats.get("avg_goals_for") and away_stats.get("avg_goals_for"):
            h = home_stats["avg_goals_for"]
            a = away_stats["avg_goals_for"]
            if h + a > 0:
                home_share = max(0.35, min(0.70, 0.5 + 0.1 * (h - a) / max(h + a, 0.1)))
        expected_home = round(expected_total * home_share, 2)
        expected_away = round(expected_total * (1 - home_share), 2)
        note_suffix = " — estimation (ajoutez API_FOOTBALL_KEY pour moyennes réelles)"

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
        "note": "Corners attendus" + note_suffix,
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


def _sample_poisson(rng: random.Random, lam: float) -> int:
    """Knuth — acceptable pour lam <= ~10 (notre cas)."""
    L = exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def goal_minutes_total(lam_h: float, lam_a: float, n_sim: int = 10000) -> Dict[str, float]:
    """Somme des minutes où les buts sont marqués.

    Ex: but 1 à 11', but 2 à 58' → total = 69'.
    Monte Carlo: buts ~ Poisson(lam_total), chaque minute ~ Uniforme(1, 90).
    """
    lam_total = lam_h + lam_a
    rng = random.Random(42)
    totals: List[int] = []
    for _ in range(n_sim):
        n = _sample_poisson(rng, lam_total)
        totals.append(sum(rng.randint(1, 90) for _ in range(n)))

    totals.sort()
    mean = sum(totals) / len(totals) if totals else 0.0

    def p_over(t: float) -> float:
        count = sum(1 for x in totals if x > t)
        return round(count / len(totals), 3)

    thresholds = [50.5, 75.5, 100.5, 125.5, 150.5, 175.5, 200.5]
    result = {
        "expected_sum_minutes": round(mean, 1),
        "note": "Somme des minutes des buts (ex: 11' + 58' = 69). Les buts en temps additionnel comptent ≤ 90.",
    }
    for t in thresholds:
        result[f"prob_over_{t}"] = p_over(t)
        result[f"prob_under_{t}"] = round(1 - p_over(t), 3)
    return result


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


def match_stats_expectation(home_stats: dict, away_stats: dict) -> Dict[str, Dict]:
    """Statistiques détaillées du match (tirs, fautes, possession, etc.).

    Utilise les vraies moyennes api-football quand disponibles, sinon heuristique
    basée sur les moyennes ligue et la force offensive.
    """
    attack_factor = 1.0
    if home_stats.get("avg_goals_for") and away_stats.get("avg_goals_for"):
        goals = home_stats["avg_goals_for"] + away_stats["avg_goals_for"]
        attack_factor = goals / (LEAGUE_AVG_GOALS_HOME + LEAGUE_AVG_GOALS_AWAY)

    baselines = {
        "shots_on_target": {"label": "Tirs cadrés", "total": 9.0, "home_share": 0.55,
                            "scales_with_attack": True, "ou": [3.5, 4.5, 5.5, 8.5, 10.5],
                            "real_key": "avg_shots_on_target"},
        "total_shots":     {"label": "Tirs vers le but", "total": 25.5, "home_share": 0.55,
                            "scales_with_attack": True, "ou": [10.5, 12.5, 14.5, 22.5, 26.5],
                            "real_key": "avg_total_shots"},
        "fouls":           {"label": "Fautes", "total": 22.0, "home_share": 0.48,
                            "scales_with_attack": False, "ou": [9.5, 10.5, 11.5, 20.5, 24.5],
                            "real_key": "avg_fouls"},
        "substitutions":   {"label": "Remplacements", "total": 10.0, "home_share": 0.50,
                            "scales_with_attack": False, "ou": [4.5, 5.5, 8.5, 10.5],
                            "real_key": None},
        "goal_kicks":      {"label": "Dégagements de but", "total": 19.0, "home_share": 0.45,
                            "scales_with_attack": False, "ou": [7.5, 9.5, 10.5, 18.5, 22.5],
                            "real_key": None},
        "throw_ins":       {"label": "Touches", "total": 45.0, "home_share": 0.50,
                            "scales_with_attack": False, "ou": [20.5, 22.5, 40.5, 48.5],
                            "real_key": None},
        "offsides":        {"label": "Hors-jeu", "total": 4.2, "home_share": 0.52,
                            "scales_with_attack": True, "ou": [1.5, 2.5, 3.5, 4.5],
                            "real_key": "avg_offsides"},
    }

    result: Dict[str, Dict] = {}
    real_count = 0
    for key, cfg in baselines.items():
        rk = cfg.get("real_key")
        if rk and rk in home_stats and rk in away_stats:
            home = round(home_stats[rk], 2)
            away = round(away_stats[rk], 2)
            total = round(home + away, 2)
            source = "api-football"
            real_count += 1
        else:
            factor = attack_factor if cfg["scales_with_attack"] else 1.0
            total = round(cfg["total"] * factor, 2)
            home = round(total * cfg["home_share"], 2)
            away = round(total - home, 2)
            source = "estimation"
        entry = {
            "label": cfg["label"],
            "expected_total": total,
            "expected_home": home,
            "expected_away": away,
            "source": source,
            "total_ou": {},
            "home_ou": {},
            "away_ou": {},
        }
        for t in cfg["ou"]:
            entry["total_ou"][f"over_{t}"] = round(_poisson_over(total, int(t) + 1), 3)
        # OU par équipe uniquement sur les seuils < moitié du total
        for t in cfg["ou"]:
            if t < total / 2:
                entry["home_ou"][f"over_{t}"] = round(_poisson_over(home, int(t) + 1), 3)
                entry["away_ou"][f"over_{t}"] = round(_poisson_over(away, int(t) + 1), 3)
        result[key] = entry

    # Possession: utiliser les vraies moyennes api-football si dispo
    if "avg_possession" in home_stats and "avg_possession" in away_stats:
        h = home_stats["avg_possession"]
        a = away_stats["avg_possession"]
        # normaliser pour que le total = 100%
        total = h + a if (h + a) > 0 else 100
        home_poss = round(100 * h / total, 1)
        real_count += 1
        poss_source = "api-football"
    else:
        home_poss = 50.0
        if home_stats.get("avg_goals_for") and away_stats.get("avg_goals_for"):
            h, a = home_stats["avg_goals_for"], away_stats["avg_goals_for"]
            if h + a > 0:
                home_poss = 50 + 10 * (h - a) / max(h + a, 0.1)
                home_poss = max(35.0, min(65.0, home_poss))
        poss_source = "estimation"
    result["possession"] = {
        "label": "Possession de balle",
        "home_pct": round(home_poss, 1),
        "away_pct": round(100 - home_poss, 1),
        "total_pct": 100.0,
        "source": poss_source,
    }

    if real_count >= 4:
        note = f"✅ {real_count} stats issues de api-football (moyennes sur 5 derniers matchs)."
    elif real_count > 0:
        note = f"⚠️ {real_count} stats réelles + estimations. Certaines données api-football manquantes."
    else:
        note = "Estimations basées sur moyennes ligue. Ajoutez API_FOOTBALL_KEY pour stats réelles."
    result["_note"] = note
    return result


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
        "goal_minutes_total": goal_minutes_total(lam_h, lam_a),
        "consecutive_goals": consecutive_goals(lam_h, lam_a),
        "goal_origin": goal_from_shot_estimate(home_stats, away_stats),
        "match_stats": match_stats_expectation(home_stats, away_stats),
    }

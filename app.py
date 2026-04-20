"""Serveur Flask — Analyst Paris.

Analyse probabiliste de matchs de football pour différents marchés de paris.
Les prédictions ne sont JAMAIS garanties. Utilisez cet outil de manière responsable.
"""
import os
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from src.data_fetcher import build_match_dossier, FootballDataClient, ApiFootballClient, _name_variants
from src.analyzer import analyse_match
from src.ai_predictor import AIPredictor

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

predictor = AIPredictor()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/competitions")
def competitions():
    fd = FootballDataClient()
    if not fd.api_key:
        return jsonify({
            "error": "FOOTBALL_DATA_API_KEY manquant",
            "hint": "Inscrivez-vous sur https://www.football-data.org/ et ajoutez la clé dans .env",
            "fallback": [
                {"code": "PL", "name": "Premier League"},
                {"code": "PD", "name": "La Liga"},
                {"code": "SA", "name": "Serie A"},
                {"code": "BL1", "name": "Bundesliga"},
                {"code": "FL1", "name": "Ligue 1"},
                {"code": "CL", "name": "Champions League"},
            ],
        }), 200
    try:
        data = fd.competitions()
        return jsonify([
            {"code": c["code"], "name": c["name"], "area": c.get("area", {}).get("name")}
            for c in data.get("competitions", []) if c.get("code")
        ])
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@app.route("/api/teams/<competition>")
def teams(competition: str):
    fd = FootballDataClient()
    if not fd.api_key:
        return jsonify({"error": "FOOTBALL_DATA_API_KEY manquant"}), 400
    try:
        data = fd.teams(competition)
        return jsonify([
            {"id": t["id"], "name": t["name"], "short": t.get("shortName")}
            for t in data.get("teams", [])
        ])
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@app.route("/api/upcoming/<competition>")
def upcoming(competition: str):
    fd = FootballDataClient()
    if not fd.api_key:
        return jsonify({
            "error": "FOOTBALL_DATA_API_KEY manquant",
            "hint": "Ajoutez la clé dans les variables d'environnement.",
        }), 400
    try:
        data = fd.upcoming_matches(competition)
        matches = []
        for m in data.get("matches", []):
            matches.append({
                "id": m.get("id"),
                "utc_date": m.get("utcDate"),
                "status": m.get("status"),
                "matchday": m.get("matchday"),
                "home": m.get("homeTeam", {}).get("name"),
                "away": m.get("awayTeam", {}).get("name"),
                "home_crest": m.get("homeTeam", {}).get("crest"),
                "away_crest": m.get("awayTeam", {}).get("crest"),
                "competition": competition,
            })
        matches.sort(key=lambda x: x.get("utc_date") or "")
        return jsonify(matches)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@app.route("/api/analyze", methods=["POST"])
def analyze():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        home = (payload.get("home") or "").strip()
        away = (payload.get("away") or "").strip()
        competition = (payload.get("competition") or "PL").strip()

        if not home or not away:
            return jsonify({"error": "Les équipes 'home' et 'away' sont requises."}), 400

        dossier = build_match_dossier(home, away, competition)
        analysis = analyse_match(dossier.get("home_stats", {}), dossier.get("away_stats", {}))
        ai_summary = predictor.synthesize(dossier, analysis)

        return jsonify({
            "match": {"home": home, "away": away, "competition": competition},
            "dossier": dossier,
            "analysis": analysis,
            "ai_summary": ai_summary,
            "disclaimer": (
                "Aucune prédiction n'est garantie. Ces probabilités sont issues d'un modèle "
                "statistique (Poisson) et d'une synthèse IA — le sport reste imprévisible. "
                "Jouez uniquement ce que vous pouvez perdre."
            ),
        })
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("analyze failed")
        return jsonify({"error": f"Erreur serveur: {exc}"}), 500


@app.route("/api/debug/af/<competition>/<name>")
def debug_af(competition: str, name: str):
    """Diagnostic: voir ce que api-football retourne pour un nom d'équipe."""
    af = ApiFootballClient()
    if not af.enabled:
        return jsonify({"error": "API_FOOTBALL_KEY non configuré"}), 400
    league_id = af.league_id(competition)
    if not league_id:
        return jsonify({"error": f"Championnat {competition} non mappé"}), 400
    season = af.current_season()
    variants = _name_variants(name)
    tries = []
    for v in variants:
        if len(v) < 3:
            continue
        try:
            data = af._get("/teams", {"search": v, "league": league_id, "season": season})
            tries.append({
                "variant": v, "season": season,
                "results_count": len(data.get("response", [])) if data else 0,
                "first_result": data["response"][0]["team"] if data and data.get("response") else None,
            })
        except Exception as exc:  # noqa: BLE001
            tries.append({"variant": v, "error": str(exc)})
    resolved = af.search_team(name, league_id, season)
    return jsonify({
        "competition": competition,
        "league_id": league_id,
        "season": season,
        "name": name,
        "variants_tried": variants,
        "searches": tries,
        "resolved_team_id": resolved,
    })


@app.errorhandler(500)
def handle_500(exc):
    return jsonify({"error": "Erreur interne du serveur", "details": str(exc)}), 500


@app.errorhandler(404)
def handle_404(exc):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Endpoint introuvable", "path": request.path}), 404
    return render_template("index.html"), 200


@app.route("/api/health")
def health():
    # Must stay minimal — used by Railway/Fly healthchecks at startup.
    return jsonify({"status": "ok"}), 200


@app.route("/api/status")
def status():
    return jsonify({
        "ai_enabled": predictor.enabled,
        "ai_provider": predictor.provider,
        "ai_model": predictor.model_label,
        "ai_init_error": predictor.init_error,
        "groq_key_detected": bool(os.getenv("GROQ_API_KEY")),
        "anthropic_key_detected": bool(os.getenv("ANTHROPIC_API_KEY")),
        "football_data_configured": bool(os.getenv("FOOTBALL_DATA_API_KEY")),
        "api_football_configured": bool(os.getenv("API_FOOTBALL_KEY")),
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_ENV") == "development")

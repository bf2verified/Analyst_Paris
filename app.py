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

from src.data_fetcher import build_match_dossier, FootballDataClient
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
    payload = request.get_json(force=True) or {}
    home = payload.get("home", "").strip()
    away = payload.get("away", "").strip()
    competition = payload.get("competition", "PL").strip()

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


@app.route("/api/health")
def health():
    # Must stay minimal — used by Railway/Fly healthchecks at startup.
    return jsonify({"status": "ok"}), 200


@app.route("/api/status")
def status():
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    football_key = os.getenv("FOOTBALL_DATA_API_KEY", "")
    return jsonify({
        "ai_enabled": predictor.enabled,
        "ai_init_error": predictor.init_error,
        "anthropic_key_detected": bool(anthropic_key),
        "anthropic_key_length": len(anthropic_key),
        "anthropic_key_prefix": anthropic_key[:10] if anthropic_key else None,
        "football_data_configured": bool(football_key),
        "football_data_key_length": len(football_key),
        "api_football_configured": bool(os.getenv("API_FOOTBALL_KEY")),
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_ENV") == "development")

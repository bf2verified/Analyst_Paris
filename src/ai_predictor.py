"""Couche de raisonnement IA — supporte Anthropic (Claude) et Groq (Llama).

Priorité: Groq si GROQ_API_KEY est défini, sinon Anthropic. Si aucun des deux,
on retombe sur la synthèse statistique pure.

IMPORTANT: Aucun modèle ne garantit de prédiction — il explique, hiérarchise,
signale les incohérences.
"""
import json
import os
from typing import Optional

import requests

try:
    from anthropic import Anthropic
except Exception:  # noqa: BLE001
    Anthropic = None  # type: ignore

ANTHROPIC_MODEL = "claude-opus-4-7"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """Tu es un analyste sportif prudent et honnête.

Ton rôle:
1. Lire les probabilités statistiques calculées (modèle de Poisson) d'un match.
2. Identifier 3 à 5 marchés où le signal statistique est le plus clair.
3. Expliquer en français, simplement, le raisonnement.
4. Signaler explicitement les risques, biais, et limites des données.

Règles absolues:
- NE JAMAIS garantir un gain. Utilise toujours des formulations probabilistes.
- NE JAMAIS encourager à augmenter les mises après une perte.
- Mentionne le jeu responsable si l'utilisateur semble miser gros.
- Si les données sont incomplètes, dis-le clairement.

Format de réponse: JSON strict uniquement (sans markdown, sans ```), avec les clés:
  "resume": string,
  "paris_conseilles": [ { "marche": string, "selection": string, "probabilite": number, "justification": string } ],
  "risques": [string],
  "conseil_gestion": string
"""


class AIPredictor:
    def __init__(self):
        self.provider: Optional[str] = None
        self.init_error: Optional[str] = None
        self._anthropic_client = None
        self._groq_key: Optional[str] = None

        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

        if groq_key:
            self._groq_key = groq_key
            self.provider = "groq"
            return

        if anthropic_key:
            if Anthropic is None:
                self.init_error = "Package anthropic non installé."
                return
            try:
                self._anthropic_client = Anthropic(api_key=anthropic_key)
                self.provider = "anthropic"
                return
            except Exception as exc:  # noqa: BLE001
                self.init_error = f"Échec init Anthropic: {exc}"
                return

        self.init_error = "Aucune clé IA détectée (GROQ_API_KEY ou ANTHROPIC_API_KEY)."

    @property
    def enabled(self) -> bool:
        return self.provider is not None

    @property
    def model_label(self) -> str:
        if self.provider == "groq":
            return f"Groq ({GROQ_MODEL})"
        if self.provider == "anthropic":
            return f"Claude ({ANTHROPIC_MODEL})"
        return "Aucun"

    def synthesize(self, dossier: dict, analysis: dict) -> dict:
        if not self.enabled:
            return _fallback(self.init_error or "IA non configurée.")

        user_payload = {
            "match": f"{dossier.get('home')} vs {dossier.get('away')}",
            "competition": dossier.get("competition"),
            "home_stats": dossier.get("home_stats"),
            "away_stats": dossier.get("away_stats"),
            "analyse_statistique": analysis,
            "warnings_donnees": dossier.get("warnings", []),
        }
        user_msg = (
            "Analyse ce dossier de match et rends UNIQUEMENT un JSON valide (sans markdown):\n\n"
            + json.dumps(user_payload, ensure_ascii=False, indent=2)
        )

        try:
            if self.provider == "groq":
                text = self._call_groq(user_msg)
            else:
                text = self._call_anthropic(user_msg)
        except Exception as exc:  # noqa: BLE001
            return _fallback(f"Erreur API {self.provider}: {exc}")

        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            return _fallback(f"Réponse {self.provider} non-JSON.", raw=text)

    def _call_groq(self, user_msg: str) -> str:
        r = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {self._groq_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 2000,
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _call_anthropic(self, user_msg: str) -> str:
        message = self._anthropic_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_msg}],
        )
        return "".join(
            b.text for b in message.content if getattr(b, "type", "") == "text"
        )


def _fallback(reason: str, raw: str = "") -> dict:
    risques = [reason]
    if raw:
        risques.append(f"Réponse brute: {raw[:300]}")
    return {
        "resume": "Synthèse IA indisponible — analyse statistique uniquement.",
        "paris_conseilles": [],
        "risques": risques,
        "conseil_gestion": "Jouez de manière responsable. Ne misez jamais plus que vous ne pouvez perdre.",
    }

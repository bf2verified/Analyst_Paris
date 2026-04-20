"""Couche de raisonnement IA utilisant Claude (Anthropic).

Claude reçoit les probabilités statistiques et produit:
 - une synthèse en langage naturel
 - les paris à «valeur» identifiés
 - les warnings/risques

IMPORTANT: Claude ne remplace pas l'analyse — il explique, hiérarchise, signale
les incohérences. Aucune prédiction n'est garantie.
"""
import json
import os
from typing import Optional

try:
    from anthropic import Anthropic
except ImportError:  # package optionnel pour exécution sans IA
    Anthropic = None  # type: ignore

MODEL_ID = "claude-opus-4-7"

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

Format de réponse: JSON strict avec les clés:
  "resume": string,
  "paris_conseilles": [ { "marche": string, "selection": string, "probabilite": number, "justification": string } ],
  "risques": [string],
  "conseil_gestion": string
"""


class AIPredictor:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.client = Anthropic(api_key=self.api_key) if (Anthropic and self.api_key) else None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def synthesize(self, dossier: dict, analysis: dict) -> dict:
        if not self.enabled:
            return {
                "resume": "IA non configurée — synthèse statistique uniquement.",
                "paris_conseilles": [],
                "risques": ["Clé ANTHROPIC_API_KEY absente."],
                "conseil_gestion": "Jouez de manière responsable. Ne misez jamais plus que vous ne pouvez perdre.",
            }

        user_payload = {
            "match": f"{dossier.get('home')} vs {dossier.get('away')}",
            "competition": dossier.get("competition"),
            "home_stats": dossier.get("home_stats"),
            "away_stats": dossier.get("away_stats"),
            "analyse_statistique": analysis,
            "warnings_donnees": dossier.get("warnings", []),
        }

        message = self.client.messages.create(
            model=MODEL_ID,
            max_tokens=2000,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Analyse ce dossier de match et rends UNIQUEMENT un JSON valide:\n\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}",
                }
            ],
        )

        text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            return {
                "resume": text,
                "paris_conseilles": [],
                "risques": ["Réponse IA non-JSON — affichage brut."],
                "conseil_gestion": "Jouez responsable.",
            }

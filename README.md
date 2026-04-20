# Analyst Paris

Application d'analyse probabiliste de matchs de football pour aider à évaluer
différents marchés de paris : **buts, corners, cartons, score exact, but affilé,
total minutes des buts, double chance, BTTS, handicap européen**, etc.

> ⚠️ **Avertissement important** — Aucune prédiction sportive n'est garantie.
> Cette application fournit des **probabilités statistiques** basées sur un modèle
> de Poisson et une synthèse IA. Le sport reste imprévisible. **Ne misez jamais
> plus que vous ne pouvez perdre.**

## Ce que fait l'app

- Récupère l'historique récent des équipes via APIs football publiques
- Calcule des **expected goals (xG)** à partir des moyennes attaque/défense
- Applique une **distribution de Poisson** pour dériver :
  - 1X2, Double chance, Over/Under 1.5/2.5/3.5
  - BTTS (les deux équipes marquent)
  - Score exact (top 6)
  - Handicap européen ±1
  - Corners, Cartons (estimations)
  - Distribution minutes des buts
  - Buts consécutifs (but affilé)
  - Origine du but (tir, tête, penalty, coup franc — priors UEFA)
- **Claude (Anthropic)** produit une synthèse en français : paris à valeur,
  risques, conseils de gestion de bankroll

## Ce que l'app ne fait PAS

- ❌ **Prédire les jeux TVBet (Poker, Wheel, Keno).** Ces jeux utilisent un
  RNG certifié : les résultats sont **mathématiquement imprévisibles**. Tout
  outil qui prétend prédire ces jeux est frauduleux.
- ❌ **Garantir un gain sur 1xBet.** Les bookmakers ont une marge (5-10%).
  Même une analyse parfaite ne garantit que des **paris à valeur positive sur
  le long terme**, pas un gain sur un pari unique.

## API IA recommandée

**Claude (Anthropic)** — `claude-opus-4-7`
- Excellente pour raisonnement multi-étapes
- Prompt caching intégré (réduit coûts de 90% sur le system prompt)
- Inscription : https://console.anthropic.com/

Alternatives viables : OpenAI `gpt-4o`, Google `gemini-1.5-pro`. Le code utilise
Claude via le SDK `anthropic` mais peut être adapté.

## Sources de données

| Source | Gratuit | Couverture |
|---|---|---|
| [football-data.org](https://www.football-data.org/) | Oui (10 req/min) | 5 grands championnats + coupes |
| [api-football.com](https://www.api-football.com/) | Freemium | Corners, cartons, tirs, lineups |

## Installation

```bash
# 1. Cloner
git clone <ce-repo>
cd Analyst_Paris

# 2. Environnement Python
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configurer les clés
cp .env.example .env
# Éditer .env et remplir ANTHROPIC_API_KEY et FOOTBALL_DATA_API_KEY

# 4. Lancer
python app.py
# Ouvrir http://localhost:5000
```

## Utilisation

1. Choisir un championnat
2. Saisir les équipes domicile et extérieur (nom exact, ex: "Manchester City")
3. Cliquer sur **Analyser le match**
4. Lire les probabilités par marché + synthèse IA

## Architecture

```
Analyst_Paris/
├── app.py                  # Serveur Flask
├── src/
│   ├── data_fetcher.py     # APIs football + cache
│   ├── analyzer.py         # Modèle Poisson, tous les marchés
│   └── ai_predictor.py     # Claude API pour synthèse
├── templates/index.html    # UI
├── static/
│   ├── style.css
│   └── app.js
├── requirements.txt
└── .env.example
```

## Jeu responsable

Si vous pensez avoir un problème de jeu :
- 🇫🇷 **Joueurs Info Service** : 09 74 75 13 13 (appel non surtaxé)
- 🌍 **BeGambleAware** : https://www.begambleaware.org/

Ne jouez jamais de l'argent dont vous avez besoin. Fixez-vous une limite
**avant** de jouer, pas pendant.

## Limites connues

- Pas de modélisation des absences (blessures, suspensions) — à ajouter via
  flux d'actualités (ex: `api-football.com/v3/injuries`).
- Modèle de Poisson suppose indépendance entre les buts des deux équipes —
  approximation raisonnable mais imparfaite.
- Les cotes 1xBet ne sont pas importées — pour détecter des paris à valeur
  réelle, comparer `probabilité × cote > 1.0`.

## Licence

MIT

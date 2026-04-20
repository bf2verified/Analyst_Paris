const form = document.getElementById('match-form');
const results = document.getElementById('results');
const loading = document.getElementById('loading');
const output = document.getElementById('output');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = {
    home: document.getElementById('home').value,
    away: document.getElementById('away').value,
    competition: document.getElementById('competition').value,
  };

  results.classList.remove('hidden');
  loading.classList.remove('hidden');
  output.innerHTML = '';

  try {
    const r = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const json = await r.json();
    loading.classList.add('hidden');
    if (!r.ok) {
      output.innerHTML = `<div class="error">${json.error || 'Erreur'}</div>`;
      return;
    }
    renderResults(json);
  } catch (err) {
    loading.classList.add('hidden');
    output.innerHTML = `<div class="error">Erreur réseau: ${err.message}</div>`;
  }
});

function pct(v) { return (v * 100).toFixed(1) + '%'; }

function pill(label, value) {
  return `<div class="prob-pill">${label}<strong>${pct(value)}</strong></div>`;
}

function renderResults(data) {
  const { match, analysis, ai_summary, dossier, disclaimer } = data;
  const m = analysis.markets;

  let html = '';

  // Match header
  html += `<div class="card"><h3>${match.home} vs ${match.away} — ${match.competition}</h3>
    <p>xG estimés : <strong>${analysis.expected_goals.home}</strong> vs <strong>${analysis.expected_goals.away}</strong>
    · Total : <strong>${analysis.expected_goals.total}</strong></p></div>`;

  // AI summary
  if (ai_summary) {
    html += `<div class="card ai-block"><h3>🧠 Synthèse IA (Claude)</h3>
      <p>${escapeHtml(ai_summary.resume || '')}</p>`;
    if (ai_summary.paris_conseilles?.length) {
      html += `<h4 style="margin-top:0.75rem;color:var(--muted);font-size:0.9rem;">Paris à valeur identifiés</h4>`;
      ai_summary.paris_conseilles.forEach(p => {
        html += `<div class="pick"><strong>${escapeHtml(p.marche)}</strong> — ${escapeHtml(p.selection)}
          <span class="pick-meta">(${pct(p.probabilite || 0)})</span>
          <div class="pick-meta">${escapeHtml(p.justification || '')}</div></div>`;
      });
    }
    if (ai_summary.risques?.length) {
      html += `<h4 style="margin-top:0.75rem;color:var(--muted);font-size:0.9rem;">Risques</h4>`;
      ai_summary.risques.forEach(r => { html += `<div class="risk">⚠️ ${escapeHtml(r)}</div>`; });
    }
    if (ai_summary.conseil_gestion) {
      html += `<p style="margin-top:0.75rem;font-size:0.9rem;"><em>💰 ${escapeHtml(ai_summary.conseil_gestion)}</em></p>`;
    }
    html += `</div>`;
  }

  // 1X2
  html += `<div class="card"><h3>1X2 & Double chance</h3><div class="market-grid">
    ${pill('Victoire domicile', m['1X2'].home)}
    ${pill('Match nul', m['1X2'].draw)}
    ${pill('Victoire extérieur', m['1X2'].away)}
    ${pill('1X (Dom. ou nul)', m.double_chance['1X'])}
    ${pill('12 (pas de nul)', m.double_chance['12'])}
    ${pill('X2 (Ext. ou nul)', m.double_chance.X2)}
    </div></div>`;

  // Over/Under
  html += `<div class="card"><h3>Total de buts (Over/Under)</h3><div class="market-grid">
    ${pill('Over 1.5', m.over_under['over_1.5'])}
    ${pill('Over 2.5', m.over_under['over_2.5'])}
    ${pill('Over 3.5', m.over_under['over_3.5'])}
    ${pill('Under 2.5', m.over_under['under_2.5'])}
    </div></div>`;

  // BTTS
  html += `<div class="card"><h3>Les deux équipes marquent</h3><div class="market-grid">
    ${pill('BTTS Oui', m.btts.yes)}
    ${pill('BTTS Non', m.btts.no)}
    </div></div>`;

  // Score exact
  html += `<div class="card"><h3>Score exact — top 6</h3><div class="market-grid">`;
  m.top_exact_scores.forEach(s => { html += pill(s.score, s.probability); });
  html += `</div></div>`;

  // Handicap
  html += `<div class="card"><h3>Handicap européen</h3><div class="market-grid">
    ${pill('Domicile -1', m.european_handicap['home_-1'])}
    ${pill('Nul (Dom -1)', m.european_handicap['home_-1_draw'])}
    ${pill('Extérieur +1', m.european_handicap['away_+1'])}
    </div></div>`;

  // Corners
  const c = analysis.corners;
  html += `<div class="card"><h3>Corners — total attendu: ${c.expected_total_corners}</h3><div class="market-grid">
    ${pill('Over 8.5', c['prob_over_8.5'])}
    ${pill('Over 9.5', c['prob_over_9.5'])}
    ${pill('Over 10.5', c['prob_over_10.5'])}
    </div><p class="pick-meta">${escapeHtml(c.note)}</p></div>`;

  // Cards
  const ca = analysis.cards;
  html += `<div class="card"><h3>Cartons — total attendu: ${ca.expected_total_cards}</h3><div class="market-grid">
    ${pill('Over 3.5', ca['prob_over_3.5'])}
    ${pill('Over 4.5', ca['prob_over_4.5'])}
    ${pill('Over 5.5', ca['prob_over_5.5'])}
    </div><p class="pick-meta">${escapeHtml(ca.note)}</p></div>`;

  // Goal minutes
  const gm = analysis.goal_minutes;
  html += `<div class="card"><h3>Minutes des buts (probabilité par intervalle)</h3><div class="market-grid">
    ${pill('0-15', gm.prob_goal_0_15)}
    ${pill('16-30', gm.prob_goal_16_30)}
    ${pill('31-45', gm.prob_goal_31_45)}
    ${pill('46-60', gm.prob_goal_46_60)}
    ${pill('61-75', gm.prob_goal_61_75)}
    ${pill('76-90', gm.prob_goal_76_90)}
    </div></div>`;

  // Consecutive
  const cg = analysis.consecutive_goals;
  html += `<div class="card"><h3>Buts consécutifs (buts affilés)</h3><div class="market-grid">
    ${pill('Domicile 2+ d\'affilée', cg.home_2_consecutive)}
    ${pill('Extérieur 2+ d\'affilée', cg.away_2_consecutive)}
    ${pill('Une équipe 2+ d\'affilée', cg.any_team_2_consecutive)}
    </div></div>`;

  // Goal origin
  const go = analysis.goal_origin;
  html += `<div class="card"><h3>Origine du but</h3><div class="market-grid">
    ${pill('Par tir', go.prob_any_goal_from_shot)}
    ${pill('De la tête', go.prob_any_goal_from_header)}
    ${pill('Sur penalty', go.prob_any_goal_from_penalty)}
    ${pill('Sur coup franc', go.prob_any_goal_from_free_kick)}
    </div><p class="pick-meta">${escapeHtml(go.note)}</p></div>`;

  // Data sources
  if (dossier.sources?.length || dossier.warnings?.length) {
    html += `<div class="card"><h3>Sources & avertissements</h3>`;
    if (dossier.sources?.length) {
      html += `<p>Sources : ${dossier.sources.join(', ')}</p>`;
    }
    dossier.warnings?.forEach(w => { html += `<div class="risk">⚠️ ${escapeHtml(w)}</div>`; });
    html += `</div>`;
  }

  html += `<div class="disclaimer">${escapeHtml(disclaimer)}</div>`;

  output.innerHTML = html;
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

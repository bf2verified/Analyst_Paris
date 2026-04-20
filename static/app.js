const competitionEl = document.getElementById('competition');
const matchesSection = document.getElementById('matches-section');
const matchesList = document.getElementById('matches-list');
const matchesLoading = document.getElementById('matches-loading');
const results = document.getElementById('results');
const loading = document.getElementById('loading');
const output = document.getElementById('output');
const backBtn = document.getElementById('back-btn');

competitionEl.addEventListener('change', loadUpcoming);
backBtn.addEventListener('click', () => {
  results.classList.add('hidden');
  matchesSection.classList.remove('hidden');
});

loadUpcoming();

async function loadUpcoming() {
  matchesSection.classList.remove('hidden');
  results.classList.add('hidden');
  matchesList.innerHTML = '';
  matchesLoading.classList.remove('hidden');
  const code = competitionEl.value;
  try {
    const r = await fetch(`/api/upcoming/${code}`);
    const json = await r.json();
    matchesLoading.classList.add('hidden');
    if (!r.ok) {
      matchesList.innerHTML = `<div class="error">${escapeHtml(json.error || 'Erreur')}${json.hint ? ' — ' + escapeHtml(json.hint) : ''}</div>`;
      return;
    }
    if (!json.length) {
      matchesList.innerHTML = `<div class="empty">Aucun match programmé pour ce championnat.</div>`;
      return;
    }
    renderMatches(json);
  } catch (err) {
    matchesLoading.classList.add('hidden');
    matchesList.innerHTML = `<div class="error">Erreur réseau: ${escapeHtml(err.message)}</div>`;
  }
}

function renderMatches(matches) {
  const byDate = {};
  matches.forEach(m => {
    const day = m.utc_date ? new Date(m.utc_date).toLocaleDateString('fr-FR', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    }) : 'Date inconnue';
    (byDate[day] ||= []).push(m);
  });

  let html = '';
  for (const [day, list] of Object.entries(byDate)) {
    html += `<div class="day-group"><h3 class="day-header">${escapeHtml(day)}</h3>`;
    list.forEach(m => {
      const time = m.utc_date ? new Date(m.utc_date).toLocaleTimeString('fr-FR', {
        hour: '2-digit', minute: '2-digit',
      }) : '--:--';
      html += `
        <div class="match-card" data-home="${escapeHtml(m.home)}" data-away="${escapeHtml(m.away)}" data-competition="${escapeHtml(m.competition)}">
          <div class="match-time">${time}</div>
          <div class="match-teams">
            <div class="team">
              ${m.home_crest ? `<img src="${escapeHtml(m.home_crest)}" alt="" class="crest">` : ''}
              <span>${escapeHtml(m.home || '?')}</span>
            </div>
            <div class="vs">vs</div>
            <div class="team">
              ${m.away_crest ? `<img src="${escapeHtml(m.away_crest)}" alt="" class="crest">` : ''}
              <span>${escapeHtml(m.away || '?')}</span>
            </div>
          </div>
          <div class="match-cta">Analyser →</div>
        </div>`;
    });
    html += `</div>`;
  }
  matchesList.innerHTML = html;

  document.querySelectorAll('.match-card').forEach(card => {
    card.addEventListener('click', () => analyseMatch({
      home: card.dataset.home,
      away: card.dataset.away,
      competition: card.dataset.competition,
    }));
  });
}

async function analyseMatch(data) {
  matchesSection.classList.add('hidden');
  results.classList.remove('hidden');
  loading.classList.remove('hidden');
  output.innerHTML = '';
  try {
    const r = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const raw = await r.text();
    loading.classList.add('hidden');
    let json;
    try {
      json = JSON.parse(raw);
    } catch {
      output.innerHTML = `<div class="error">Serveur a répondu en HTML (code ${r.status}). Extrait: <pre>${escapeHtml(raw.slice(0, 400))}</pre></div>`;
      return;
    }
    if (!r.ok) {
      output.innerHTML = `<div class="error">${escapeHtml(json.error || 'Erreur')}${json.details ? ' — ' + escapeHtml(json.details) : ''}</div>`;
      return;
    }
    renderResults(json);
  } catch (err) {
    loading.classList.add('hidden');
    output.innerHTML = `<div class="error">Erreur réseau: ${escapeHtml(err.message)}</div>`;
  }
}

function pct(v) { return (v * 100).toFixed(1) + '%'; }
function pill(label, value) {
  return `<div class="prob-pill">${escapeHtml(label)}<strong>${pct(value)}</strong></div>`;
}

function renderResults(data) {
  const { match, analysis, ai_summary, dossier, disclaimer } = data;
  const m = analysis.markets;
  let html = '';

  html += `<div class="card"><h3>${escapeHtml(match.home)} vs ${escapeHtml(match.away)} — ${escapeHtml(match.competition)}</h3>
    <p>xG estimés : <strong>${analysis.expected_goals.home}</strong> vs <strong>${analysis.expected_goals.away}</strong>
    · Total : <strong>${analysis.expected_goals.total}</strong></p></div>`;

  if (ai_summary) {
    html += `<div class="card ai-block"><h3>🧠 Synthèse IA</h3>
      <p>${escapeHtml(ai_summary.resume || '')}</p>`;
    if (ai_summary.paris_conseilles?.length) {
      html += `<h4 class="sub-head">Paris à valeur identifiés</h4>`;
      ai_summary.paris_conseilles.forEach(p => {
        html += `<div class="pick"><strong>${escapeHtml(p.marche)}</strong> — ${escapeHtml(p.selection)}
          <span class="pick-meta">(${pct(p.probabilite || 0)})</span>
          <div class="pick-meta">${escapeHtml(p.justification || '')}</div></div>`;
      });
    }
    if (ai_summary.risques?.length) {
      html += `<h4 class="sub-head">Risques</h4>`;
      ai_summary.risques.forEach(r => { html += `<div class="risk">⚠️ ${escapeHtml(r)}</div>`; });
    }
    if (ai_summary.conseil_gestion) {
      html += `<p class="bankroll"><em>💰 ${escapeHtml(ai_summary.conseil_gestion)}</em></p>`;
    }
    html += `</div>`;
  }

  html += `<div class="card"><h3>1X2 & Double chance</h3><div class="market-grid">
    ${pill('Victoire domicile', m['1X2'].home)}
    ${pill('Match nul', m['1X2'].draw)}
    ${pill('Victoire extérieur', m['1X2'].away)}
    ${pill('1X (Dom. ou nul)', m.double_chance['1X'])}
    ${pill('12 (pas de nul)', m.double_chance['12'])}
    ${pill('X2 (Ext. ou nul)', m.double_chance.X2)}
    </div></div>`;

  html += `<div class="card"><h3>Total de buts</h3><div class="market-grid">
    ${pill('Over 1.5', m.over_under['over_1.5'])}
    ${pill('Over 2.5', m.over_under['over_2.5'])}
    ${pill('Over 3.5', m.over_under['over_3.5'])}
    ${pill('Under 2.5', m.over_under['under_2.5'])}
    </div></div>`;

  html += `<div class="card"><h3>BTTS — Les deux équipes marquent</h3><div class="market-grid">
    ${pill('Oui', m.btts.yes)}${pill('Non', m.btts.no)}
    </div></div>`;

  html += `<div class="card"><h3>Score exact — top 6</h3><div class="market-grid">`;
  m.top_exact_scores.forEach(s => { html += pill(s.score, s.probability); });
  html += `</div></div>`;

  html += `<div class="card"><h3>Handicap européen</h3><div class="market-grid">
    ${pill('Domicile -1', m.european_handicap['home_-1'])}
    ${pill('Nul (Dom -1)', m.european_handicap['home_-1_draw'])}
    ${pill('Extérieur +1', m.european_handicap['away_+1'])}
    </div></div>`;

  const c = analysis.corners;
  html += `<div class="card"><h3>Corners — total attendu: ${c.expected_total_corners}</h3><div class="market-grid">
    ${pill('Over 8.5', c['prob_over_8.5'])}
    ${pill('Over 9.5', c['prob_over_9.5'])}
    ${pill('Over 10.5', c['prob_over_10.5'])}
    </div><p class="pick-meta">${escapeHtml(c.note)}</p></div>`;

  const ca = analysis.cards;
  html += `<div class="card"><h3>Cartons — total attendu: ${ca.expected_total_cards}</h3><div class="market-grid">
    ${pill('Over 3.5', ca['prob_over_3.5'])}
    ${pill('Over 4.5', ca['prob_over_4.5'])}
    ${pill('Over 5.5', ca['prob_over_5.5'])}
    </div><p class="pick-meta">${escapeHtml(ca.note)}</p></div>`;

  const gm = analysis.goal_minutes;
  html += `<div class="card"><h3>Minutes des buts</h3><div class="market-grid">
    ${pill('0-15', gm.prob_goal_0_15)}
    ${pill('16-30', gm.prob_goal_16_30)}
    ${pill('31-45', gm.prob_goal_31_45)}
    ${pill('46-60', gm.prob_goal_46_60)}
    ${pill('61-75', gm.prob_goal_61_75)}
    ${pill('76-90', gm.prob_goal_76_90)}
    </div></div>`;

  const cg = analysis.consecutive_goals;
  html += `<div class="card"><h3>Buts consécutifs</h3><div class="market-grid">
    ${pill('Domicile 2+', cg.home_2_consecutive)}
    ${pill('Extérieur 2+', cg.away_2_consecutive)}
    ${pill('Une équipe 2+', cg.any_team_2_consecutive)}
    </div></div>`;

  const go = analysis.goal_origin;
  html += `<div class="card"><h3>Origine du but</h3><div class="market-grid">
    ${pill('Par tir', go.prob_any_goal_from_shot)}
    ${pill('De la tête', go.prob_any_goal_from_header)}
    ${pill('Sur penalty', go.prob_any_goal_from_penalty)}
    ${pill('Sur coup franc', go.prob_any_goal_from_free_kick)}
    </div><p class="pick-meta">${escapeHtml(go.note)}</p></div>`;

  if (dossier.sources?.length || dossier.warnings?.length) {
    html += `<div class="card"><h3>Sources & avertissements</h3>`;
    if (dossier.sources?.length) html += `<p>Sources : ${dossier.sources.join(', ')}</p>`;
    dossier.warnings?.forEach(w => { html += `<div class="risk">⚠️ ${escapeHtml(w)}</div>`; });
    html += `</div>`;
  }

  html += `<div class="disclaimer">${escapeHtml(disclaimer)}</div>`;
  output.innerHTML = html;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

/* Modul-Bewertung (Panduan Penilaian Deutschkurs): Sterne, Level-Ampel, Namen der Aspekte und Codes, kompakte
   Anzeige einer Bewertung und ein Verlauf — gemeinsam fuer Erfassung, Auswertung, Kandidatenprofil und Portal.
   Gerechnet wird nichts: Punkte und Level kommen fertig vom Server (`result`), Grenzen aus `rules`. */
const LessonView = (() => {
  const {esc, t, icon, fmtDate, fmtNum} = App;
  const BEHAVIOR = ['pu', 'mi', 'ha'];

  const stars = (n, max) => (n == null ? `<span class="meta" title="${esc(t('lr_blank'))}">–</span>`
    : `<span class="stars" role="img" aria-label="${esc(t('lr_stars_aria', {n, max}))}">${
      Array.from({length: max}, (_, i) => icon('star', i < n ? 'on' : 'off')).join('')}</span>`);
  const levelBadge = level => (level ? `<span class="lvl lvl-${esc(level.toLowerCase())}" title="${esc(t('lr_level_' + level))}">${esc(level)}</span>` : '–');
  const aspectName = a => t('lr_a_' + a);
  const behaviorName = b => t('lr_b_' + b);
  const codeName = c => (c === 'L' ? t('lr_code_l') : aspectName(c.toLowerCase()));
  const codesText = list => (list && list.length ? list.map(codeName).join(', ') : '–');
  const points = (res, rules) => (res && res.complete ? t('lr_points', {n: res.total, max: rules.total_max}) : t('lr_incomplete'));
  const num = x => (x == null ? '–' : String(x));
  const unitText = u => (u ? t('lr_unit', {n: u}) : '');
  const haText = (ha, rules) => (ha == null ? t('lr_no_homework_short', {n: rules.ha_without_homework}) : String(ha));
  const trend = d => (d == null ? '–' : `<span class="lr-trend ${d > 0 ? 'up' : d < 0 ? 'down' : ''}">${d > 0 ? '+' : ''}${esc(fmtNum(d))}</span>`);

  /* Eine Bewertung kompakt: Sterne je Aspekt, Lernverhalten, Punkte + Level, Staerke/Ziel (+ Notiz fuers Team).
     Leere Werte stehen als „–". */
  function compactHtml(r, rules, {note = true} = {}) {
    return `<div class="lr-cells">${rules.aspects.map(a => `<span title="${esc(aspectName(a))}">${esc(a.toUpperCase())} ${stars(r[a], rules.aspect_max)}</span>`).join('')}</div>
      <div class="lr-cells meta">${BEHAVIOR.map(b => `<span>${esc(behaviorName(b))}: ${esc(b === 'ha' ? haText(r.ha, rules) : num(r[b]))}</span>`).join('')}</div>
      <div class="lr-cells"><span class="lr-result">${esc(points(r.result, rules))} ${levelBadge(r.result.level)}</span>
        <span>${esc(t('lr_strength'))}: <b>${esc(codesText(r.strength))}</b></span>
        <span>${esc(t('lr_target'))}: <b>${esc(codesText(r.target))}</b></span></div>
      ${note && r.note ? `<p class="meta wrap-text">${esc(r.note)}</p>` : ''}`;
  }

  /* Verlauf (neueste zuerst) als Tabelle: Datum, Modul/Einheit (der Bewertung), Sterne, Punkte, Level, Staerke, Ziel. */
  function historyHtml(list, rules, {note = true, emptyText} = {}) {
    if (!list.length) return App.emptyHtml(emptyText || t('lr_none'));
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('th_date'))}</th><th>${esc(t('page_module'))}</th>
      ${rules.aspects.map(a => `<th class="c" title="${esc(aspectName(a))}">${esc(a.toUpperCase())}</th>`).join('')}
      <th class="c">${esc(t('lr_th_points'))}</th><th class="c">${esc(t('lr_th_level'))}</th>
      <th>${esc(t('lr_strength'))}</th><th>${esc(t('lr_target'))}</th>${note ? `<th>${esc(t('lr_note'))}</th>` : ''}</tr></thead>
      <tbody>${list.map(r => `<tr><td class="nw">${esc(fmtDate(r.session.date))}</td>
        <td>${esc(r.module.name)} <span class="meta">${esc(unitText(r.unit))}</span></td>
        ${rules.aspects.map(a => `<td class="c nw">${stars(r[a], rules.aspect_max)}</td>`).join('')}
        <td class="c nw">${esc(points(r.result, rules))}</td><td class="c">${levelBadge(r.result.level)}</td>
        <td>${esc(codesText(r.strength))}</td><td>${esc(codesText(r.target))}</td>
        ${note ? `<td class="wrap">${esc(r.note || '')}</td>` : ''}</tr>`).join('')}</tbody></table></div>`;
  }

  /* Level-Legende aus den Regel-Zahlen des Servers. */
  const levelsHtml = rules => `<div class="lr-levels">${rules.levels.map(l => `<div>${levelBadge(l.code)}
    <span>${esc(t('lr_level_range', {min: l.min, max: l.max}))} · ${esc(t('lr_level_' + l.code))}</span></div>`).join('')}</div>`;

  return {stars, levelBadge, aspectName, behaviorName, codeName, codesText, points, unitText, haText, trend, compactHtml,
          historyHtml, levelsHtml, BEHAVIOR};
})();

/* Overall rating: names of parts/categories/kinds, value or "Ausstehend" (pending), period selection and download
   links — shared by ranking and Azubi report. Nothing is calculated: values and rules come ready from the server. */
const OverallView = (() => {
  const {esc, t, fmtNum, fmtDate, days, todayIso} = App;
  const PRESETS = ['all', 'month', 'last_month', 'custom'];

  const partName = k => t('ov_part_' + k);
  const categoryName = c => t('rt_cat_' + c);
  const kindName = k => t('rt_kind_' + k);
  const pending = () => `<span class="badge warn">${esc(t('ov_pending'))}</span>`;
  const score = value => (value == null ? pending() : `<b>${esc(fmtNum(value))}</b>`);

  /* Period from the preset — null = whole history. */
  function period(state) {
    const today = todayIso();
    switch (state.preset) {
      case 'month': return {from: days.monthStart(today), to: today};
      case 'last_month': return {from: days.addMonths(today, -1), to: days.add(days.monthStart(today), -1)};
      case 'custom': return {from: state.from || days.monthStart(today), to: state.to || today};
      default: return null;
    }
  }

  function readState(params) {
    return {preset: PRESETS.includes(params.get('preset')) ? params.get('preset') : 'all',
            from: params.get('from') || '', to: params.get('to') || ''};
  }

  /* Query parameters (without format) for API and downloads. */
  function query(state, extra) {
    const p = new URLSearchParams(extra || {});
    const x = period(state);
    if (x) { p.set('from', x.from); p.set('to', x.to); }
    return p;
  }

  function periodFields(state) {
    const opt = v => `<option value="${v}"${v === state.preset ? ' selected' : ''}>${esc(t('ov_preset_' + v))}</option>`;
    const x = period(state) || {from: '', to: ''};
    const hidden = state.preset === 'custom' ? '' : ' hidden';
    return `<label class="meta">${esc(t('rp_period'))}<select class="input" name="preset">${PRESETS.map(opt).join('')}</select></label>
      <label class="meta"${hidden} data-custom>${esc(t('rp_from'))}<input class="input" type="date" name="from" value="${esc(x.from)}"></label>
      <label class="meta"${hidden} data-custom>${esc(t('rp_to'))}<input class="input" type="date" name="to" value="${esc(x.to)}"></label>`;
  }

  /* Take a change of the period fields into `state`; true = period changed. */
  function applyPeriod(state, target, root) {
    const {name, value} = target;
    if (!['preset', 'from', 'to'].includes(name)) return false;
    if (name === 'preset' && value === 'custom') { const x = period(state) || {}; state.from = x.from || ''; state.to = x.to || ''; }
    state[name] = value;
    root.querySelectorAll('[data-custom]').forEach(el => { el.hidden = state.preset !== 'custom'; });
    return true;
  }

  const periodText = p => (p.from ? `${App.fmtDate(p.from)} – ${App.fmtDate(p.to)}` : t('ov_preset_all'));
  const weightsText = rules => rules.parts.map(k => `${partName(k)} ${rules.weights[k]} %`).join(' + ');

  const downloads = url => `<div class="tools no-print">
    <a class="btn ghost sm" href="${esc(url('xlsx'))}" download>${App.icon('file')} ${esc(t('ov_excel'))}</a>
    <a class="btn ghost sm" href="${esc(url('pdf'))}" download>${App.icon('file')} ${esc(t('ov_pdf'))}</a></div>`;

  /* Definition list "label -> value" (– if empty) — shared by aspect derivation and header data. */
  const fact = (label, value) => `<dt>${esc(label)}</dt><dd>${value == null || value === '' || (Array.isArray(value) && !value.length)
    ? '–' : esc(Array.isArray(value) ? value.join(', ') : value)}</dd>`;
  const levelBadge = level => (level ? `<span class="lvl lvl-${esc(level.toLowerCase())}">${esc(level)}</span>` : '–');

  function reportHtml(p, r) {
    if (p.score == null) return App.emptyHtml(t('ov_report_none'));
    return `<dl class="facts">
      ${fact(t('ov_window'), `${fmtDate(p.from)} – ${fmtDate(p.to)} · ${t('ov_workdays', {n: p.workdays})}`)}
      ${fact(t('ov_hours'), t('ov_hours_text', {h: fmtNum(p.hours), target: p.target_hours, per: r.hours_per_workday,
        cap: r.day_hours_cap, pct: fmtNum(p.hours_percent)}))}
      ${fact(t('ov_regularity'), t('ov_regularity_text', {n: p.days_reported, of: p.workdays, pct: fmtNum(p.regularity_percent)}))}
      ${fact(t('ov_detail'), t('ov_detail_text', {pct: fmtNum(p.detail_percent), chars: r.detail_full_chars}))}
      </dl><p class="meta">${esc(t('ov_report_parts', r.report_parts))}</p>`;
  }

  function germanHtml(p, r) {
    const a = p.attendance;
    const att = t('ov_attendance_text', {p: a.present, l: a.late, a: a.absent, e: a.excused,
      rate: a.rate == null ? '–' : fmtNum(a.rate * 100) + ' %'});
    if (p.score == null) return `${App.emptyHtml(t('ov_german_none'))}<dl class="facts">${fact(t('ov_attendance'), att)}</dl>`;
    return `<dl class="facts">
      ${fact(t('ov_lessons'), t('ov_lessons_text', {n: p.count, avg: fmtNum(p.average_total), max: r.german_max, pct: fmtNum(p.lessons_percent)}))}
      <dt>${esc(t('ov_latest_level'))}</dt><dd>${levelBadge(p.latest_level)}</dd>
      ${fact(t('ov_attendance'), att)}</dl>
      <p class="meta">${esc(t('ov_german_parts', r.german_parts))}</p>`;
  }

  function ratingPartHtml(p, r) {
    if (p.score == null) return App.emptyHtml(t('ov_ratings_none'));
    const notes = (p.notes || []).filter(n => n.note);
    const months = Object.entries(p.months || {});
    return `<dl class="facts">${fact(t('rb_count'), String(p.count))}
      ${r.categories.map(c => fact(categoryName(c), fmtNum(p[c]))).join('')}
      ${months.map(([m, x]) => fact(t('rt_month_n', {n: m}), t('ov_month_text', {score: fmtNum(x.score), mean: fmtNum(x.mean), n: x.count}))).join('')}</dl>
      ${months.length > 1 ? `<p class="meta">${esc(t('ov_months_rule'))}</p>` : ''}
      ${notes.length ? `<div class="notelist"><div class="meta">${esc(t('ov_rating_notes'))}</div>
        <ul>${notes.map(n => `<li>${n.month ? `<span class="badge">${esc(t('rt_month_n', {n: n.month}))}</span> ` : ''}${n.rater ? `<b>${esc(n.rater)}:</b> ` : ''}${esc(n.note)}</li>`).join('')}</ul></div>` : ''}`;
  }

  /* Derivation of ONE part from its aspects — for the Azubi detail page and for expanding in the ranking. */
  const partDetailHtml = (k, p, rules) => (k === 'report' ? reportHtml(p, rules)
    : k === 'german' ? germanHtml(p, rules) : ratingPartHtml(p, rules));

  /* Month comparison: signed change ("+5,2", "−3", "±0") and the trend badge (icon + label, never colour alone). */
  const signed = d => (d == null ? '–' : `${d > 0 ? '+' : d < 0 ? '−' : '±'}${fmtNum(Math.abs(d))}`);
  const TREND_LOOK = {IMPROVED: ['ok', 'trending'], DECLINED: ['warn', 'trending-down'], STAGNANT: ['', 'minus'], OPEN: ['muted', '']};
  const trendBadge = trend => {
    const [cls, ic] = TREND_LOOK[trend] || ['', ''];
    return `<span class="badge trend ${cls}">${ic ? App.icon(ic) : ''}${esc(t('mv_trend_' + trend))}</span>`;
  };

  return {PRESETS, partName, categoryName, kindName, pending, score, period, readState, query, periodFields,
          applyPeriod, periodText, weightsText, downloads, fact, partDetailHtml, signed, trendBadge};
})();

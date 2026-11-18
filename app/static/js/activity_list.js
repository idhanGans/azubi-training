/* Verlaufs-Eintraege darstellen (Verlauf-Seite + Kandidatenprofil): Zeit, wer, Aktion, Datensatz, Alt → Neu, Grund. */
const ActivityList = (() => {
  const {esc, t, fmtDate, fmtDateTime, fmtNum} = App;
  const FIELD_KEYS = {name: 'f_name', nickname: 'f_nickname', email: 'f_email', fach: 'f_fach',
    abteilung: 'f_abteilung', msh_user: 'f_login', period: 'f_date', hours: 'f_hours', lang: 'f_lang',
    tech: 'f_tech', station: 'f_station', learned: 'f_learned', phone: 'f_phone', date_of_birth: 'f_birth',
    target_occupation: 'f_target_occupation', status: 'f_status', current_level: 'f_level_current',
    target_level: 'f_level_target', start_date: 'f_start', expected_completion_date: 'f_end',
    code: 'f_code', sort_order: 'f_order', position: 'f_order', active: 'active', program: 'f_program',
    description: 'f_description', qualification: 'f_qualification', specialization: 'f_specialization',
    levels: 'f_levels_taught', availability: 'f_availability', level: 'vl_f_level', module: 'page_module',
    instructor: 'f_instructor', date: 'f_date', start: 'f_start_time', end: 'f_end_time', room: 'f_room',
    location: 'f_location', online_url: 'f_online_url', cancel_reason: 'f_cancel_reason', notes: 'f_notes_internal',
    duration_hours: 'f_duration', learning_objectives: 'f_objectives', type: 'f_type', title: 'f_title', url: 'f_url',
    file_name: 'f_file', passing_percent: 'tpl_passing', archived_at: 'vl_f_archived_at',
    archived_by: 'vl_f_archived_by', struktur: 'vl_f_structure', fertigkeiten: 'tpl_skill'};
  /* Status-Werte je Bereich (Praefix der Aktion, z.B. session.update) -> Schluessel-Praefix in i18n.js */
  const VALUE_PREFIX = {course: 'cs_', session: 'ss_', instructor: 'is_', module: 'status_', curriculum: 'status_',
                        material: 'type_'};
  const LINKS = {trainee: id => `/candidates/${id}`, course: id => `/courses/${id}`, instructor: () => '/instructors',
                 assessment_template: () => '/assessment-templates', module: id => `/modules/${id}`};

  /* Verschachtelte Felder kommen als „fertigkeiten › Lesen" — jeder Teil einzeln. */
  const fieldLabel = k => k.split(' › ').map(part => (FIELD_KEYS[part] ? t(FIELD_KEYS[part]) : part)).join(' › ');
  const actionLabel = a => (I18N['act_' + a.replace('.', '_')] ? t('act_' + a.replace('.', '_')) : a);
  /* Datensatz-Art: „trainee" -> „Kandidat", „candidate-status" -> „Kandidaten-Status" */
  const entityLabel = e => {
    const key = 'vl_entity_' + e.replace(/-/g, '_');
    return I18N[key] ? t(key) : e;
  };

  function value(v, area) {
    if (v == null || v === '') return '–';
    if (typeof v === 'boolean') return t(v ? 'yes' : 'no');
    if (typeof v === 'number') return fmtNum(v, 2);
    if (typeof v === 'string' && /^[A-Z][A-Z_]+$/.test(v) && VALUE_PREFIX[area] && I18N[VALUE_PREFIX[area] + v]) {
      return t(VALUE_PREFIX[area] + v);
    }
    if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)) return fmtDate(v);
    if (Array.isArray(v)) {
      return v.map(x => (x && x.weekday != null ? `${t('wd_' + x.weekday)} ${x.start}–${x.end}` : value(x, area)))
        .join(', ') || '–';
    }
    if (typeof v === 'object') return JSON.stringify(v);
    return String(v);
  }

  function changesHtml(changes, area) {
    if (!changes || !changes.length) return '';
    return `<ul class="changes">${changes.map(c => `<li><span class="mut">${esc(fieldLabel(c.field))}:</span> ${c.structure
      ? esc(t('vl_structure_changed'))
      : `<s>${esc(value(c.old, area))}</s> → <b>${esc(value(c.new, area))}</b>`}</li>`).join('')}</ul>`;
  }

  function entity(a) {
    if (!a.entity_name) return '';
    const link = LINKS[a.entity_type] && a.entity_id ? LINKS[a.entity_type](a.entity_id) : null;
    return link ? `<a href="${esc(link)}">${esc(a.entity_name)}</a>` : `<b>${esc(a.entity_name)}</b>`;
  }

  function rowsHtml(entries, {showEntity = true} = {}) {
    return entries.map(a => `<tr><td class="nw">${esc(fmtDateTime(a.created_at))}</td>
      <td class="nw">${esc(a.actor_name || a.actor)}${a.actor_name ? `<div class="meta">${esc(a.actor)}</div>` : ''}</td>
      <td class="nw">${esc(actionLabel(a.action))}</td>
      <td class="wrap">${showEntity && a.entity_name ? `${entity(a)} · ` : ''}${esc(a.summary || '')}
        ${changesHtml(a.changes, a.action.split('.')[0])}${a.reason ? `<div class="meta">${esc(t('vl_reason'))}: ${esc(a.reason)}</div>` : ''}</td></tr>`).join('');
  }

  function tableHtml(entries, opts) {
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('vl_time'))}</th><th>${esc(t('vl_actor'))}</th>
      <th>${esc(t('vl_action'))}</th><th>${esc(t('vl_detail'))}</th></tr></thead><tbody>${rowsHtml(entries, opts)}</tbody></table></div>`;
  }

  return {tableHtml, rowsHtml, actionLabel, entityLabel};
})();

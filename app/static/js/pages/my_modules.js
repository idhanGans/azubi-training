/* Kandidat: Module des eigenen Curriculums — Stand, Lernziele, Lernmaterial (Dateien ueber /api/my-materials). */
(() => {
  const {$, esc, t, api, fmtNum} = App;
  const host = $('#page');
  let curricula = null;
  const ICON = {done: 'check', current: 'circle-dot', open: 'circle'};

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      curricula = (await api('GET', '/api/my-modules')).curricula;
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  const size = bytes => (bytes == null ? '' : bytes < 1048576 ? `${fmtNum(bytes / 1024, 0)} KB` : `${fmtNum(bytes / 1048576, 1)} MB`);

  function materialHtml(m) {
    const href = m.has_file ? `/api/my-materials/${m.id}/file` : m.url;
    const extra = m.has_file ? [m.file_name, size(m.size_bytes)].filter(Boolean).join(' · ') : t('mm_link');
    return `<li class="material"><span class="badge">${esc(t('type_' + m.type))}</span>
      ${href ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(m.title)}</a>` : `<b>${esc(m.title)}</b>`}
      <span class="meta">${esc(extra)}</span>${m.description ? `<div class="meta wrap-text">${esc(m.description)}</div>` : ''}</li>`;
  }

  function moduleHtml(m) {
    return `<details class="card module-card ${m.state}" id="module-${m.id}"${m.state === 'current' ? ' open' : ''}>
      <summary>${App.icon(ICON[m.state], 'mstate ' + m.state)} <b>${esc(m.name)}</b>
        <span class="badge ${m.state === 'current' ? 'ok' : ''}">${esc(t('pr_state_' + m.state))}</span></summary>
      ${m.description ? `<p class="wrap-text">${esc(m.description)}</p>` : ''}
      ${m.learning_objectives.length ? `<h4>${esc(t('mm_objectives'))}</h4><ul>${m.learning_objectives.map(o => `<li>${esc(o)}</li>`).join('')}</ul>` : ''}
      <h4>${esc(t('mm_materials'))}</h4>
      ${m.materials.length ? `<ul class="plain materials">${m.materials.map(materialHtml).join('')}</ul>` : `<p class="meta">${esc(t('mm_no_materials'))}</p>`}
    </details>`;
  }

  function render() {
    if (!curricula.length) { host.innerHTML = `<div class="card">${App.emptyHtml(t('mm_none'))}</div>`; return; }
    host.innerHTML = curricula.map(c => `<div class="card"><h2>${esc(c.curriculum.program)} · ${esc(c.curriculum.level.code)}</h2>
        ${Charts.meter(c.percent, t('pr_modules_done', {c: c.completed, n: c.total, p: `${fmtNum(c.percent, 1)} %`}))}
        <p class="meta">${esc(t('pr_modules_done', {c: c.completed, n: c.total, p: `${fmtNum(c.percent, 1)} %`}))} · ${esc(c.course.name)}</p></div>
      ${c.modules.map(moduleHtml).join('')}`).join('');
    const target = location.hash && document.querySelector(location.hash);
    if (target) { target.open = true; target.scrollIntoView(); }
  }

  App.onRerender(() => curricula && render());
  load();
})();

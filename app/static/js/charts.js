/* Small SVG charts without a library: line (trend in %), columns (per week in %), progress bar.
   Rules: one colour (--viz-series), thin marks, hairline grid, tooltip by mouse AND keyboard,
   every chart with a table view (values never only in the tooltip). Labels via textContent. */
const Charts = (() => {
  const {esc, t, fmtNum} = App;
  const NS = 'http://www.w3.org/2000/svg';
  let uid = 0;

  function el(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(node);
    return node;
  }
  const pct = v => (v == null ? '–' : `${fmtNum(v, 1)} %`);

  /* Frame: <figure> with title, chart host, tooltip and expandable table. */
  function frame(title, table, caption) {
    const id = `viz${++uid}`;
    return {id, html: `<figure class="viz" id="${id}">${title ? `<figcaption>${esc(title)}${caption ? ` <span class="meta">${esc(caption)}</span>` : ''}</figcaption>` : ''}
      <div class="viz-plot"></div><div class="viz-tip" role="status" hidden></div>
      <details class="viz-table"><summary>${esc(t('viz_table'))}</summary>
        <div class="tbl-wrap"><table class="tbl"><thead><tr>${table.head.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead>
        <tbody>${table.rows.map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details></figure>`};
  }

  function showTip(fig, x, y, value, label) {
    const tip = fig.querySelector('.viz-tip');
    tip.textContent = '';
    const strong = document.createElement('b');
    strong.textContent = value;
    const span = document.createElement('span');
    span.textContent = label;
    tip.append(strong, span);
    tip.hidden = false;
    const box = fig.querySelector('.viz-plot').getBoundingClientRect();
    const left = Math.min(Math.max(x - tip.offsetWidth / 2, 0), box.width - tip.offsetWidth);
    tip.style.left = `${left}px`;
    tip.style.top = `${Math.max(y - tip.offsetHeight - 10, 0)}px`;
  }

  /* Shared by line + columns: axis 0–100 %, points with hover/keyboard.
     Drawn in the REAL width of the space — otherwise the text would be scaled along. */
  function plot(fig, {width: fallback, height, points, draw, ticks, unit = ' %'}) {
    const width = Math.round(fig.querySelector('.viz-plot').clientWidth) || fallback;
    const pad = {l: 34, r: 14, t: 10, b: 24};
    const svg = el('svg', {viewBox: `0 0 ${width} ${height}`, role: 'img', tabindex: '0', class: 'viz-svg',
                           'aria-label': fig.querySelector('figcaption') ? fig.querySelector('figcaption').textContent : ''});
    const y = v => pad.t + (1 - v / 100) * (height - pad.t - pad.b);
    (ticks || [0, 50, 100]).forEach(v => {
      el('line', {x1: pad.l, x2: width - pad.r, y1: y(v), y2: y(v), class: v === 0 ? 'viz-base' : 'viz-grid'}, svg);
      el('text', {x: pad.l - 6, y: y(v) + 4, 'text-anchor': 'end', class: 'viz-axis'}, svg).textContent = `${v}${unit}`;
    });
    const n = points.length;
    // time axis if the points carry a date (gaps = real days), otherwise evenly spaced
    const t0 = points[0].time, t1 = points[n - 1].time, span = width - pad.l - pad.r - 24;
    const timed = n > 1 && t0 != null && t1 > t0;
    const x = i => (n === 1 ? (pad.l + width - pad.r) / 2
      : pad.l + 12 + (timed ? (points[i].time - t0) / (t1 - t0) : i / (n - 1)) * span);
    const hair = el('line', {y1: pad.t, y2: height - pad.b, class: 'viz-cross', visibility: 'hidden'}, svg);
    const marks = draw(svg, {x, y, pad, width, height});
    // axis labels from right to left; one too close to the previous is left out (tooltip/table have all)
    let lastX = Infinity;
    for (let i = n - 1; i >= 0; i--) {
      if (lastX - x(i) < 46) continue;
      el('text', {x: x(i), y: height - 6, 'text-anchor': 'middle', class: 'viz-axis'}, svg).textContent = points[i].short;
      lastX = x(i);
    }
    fig.querySelector('.viz-plot').appendChild(svg);
    let active = -1;
    function focus(i) {
      active = i;
      marks.forEach((m, j) => m && m.classList.toggle('on', j === i));
      if (i < 0) { hair.setAttribute('visibility', 'hidden'); fig.querySelector('.viz-tip').hidden = true; return; }
      hair.setAttribute('x1', x(i));
      hair.setAttribute('x2', x(i));
      hair.setAttribute('visibility', 'visible');
      const scale = svg.getBoundingClientRect().width / width;
      const p = points[i];
      showTip(fig, x(i) * scale, y(p.value == null ? 0 : p.value) * scale, p.valueText, p.label);
    }
    svg.addEventListener('pointermove', ev => {
      const rect = svg.getBoundingClientRect();
      const px = (ev.clientX - rect.left) * width / rect.width;
      let best = 0;
      points.forEach((_, i) => { if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i; });
      focus(best);
    });
    svg.addEventListener('pointerleave', () => focus(-1));
    svg.addEventListener('blur', () => focus(-1));
    svg.addEventListener('keydown', ev => {
      if (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft') {
        ev.preventDefault();
        focus(Math.max(0, Math.min(n - 1, (active < 0 ? n - 1 : active + (ev.key === 'ArrowRight' ? 1 : -1)))));
      } else if (ev.key === 'Escape') focus(-1);
    });
    svg.addEventListener('focus', () => focus(n - 1));
  }

  /* Line: points [{value (0–100), short (axis), label (tooltip), valueText}] — the last value is labelled directly.
     `unit` = suffix of the axis labels (default " %"; "" for points 0–100). */
  function line(host, {title, caption, points, width = 560, height = 220, table, unit}) {
    const f = frame(title, table, caption);
    host.insertAdjacentHTML('beforeend', f.html);
    const fig = host.querySelector(`#${f.id}`);
    plot(fig, {width, height, points, unit, ticks: height < 170 ? [0, 50, 100] : [0, 25, 50, 75, 100], draw: (svg, {x, y, width}) => {
      const d = points.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.value)}`).join(' ');
      if (points.length > 1) el('path', {d, class: 'viz-line'}, svg);
      const dots = points.map((p, i) => el('circle', {cx: x(i), cy: y(p.value), r: 4, class: 'viz-dot'}, svg));
      const last = points[points.length - 1];
      const lx = x(points.length - 1);
      el('text', {x: lx, y: y(last.value) - 10, 'text-anchor': lx > width - 60 ? 'end' : 'middle', class: 'viz-label'}, svg)
        .textContent = last.valueText;
      return dots;
    }});
  }

  /* Columns per category (e.g. week): value null = no countable entries (no column). */
  function columns(host, {title, caption, points, width = 560, height = 200, table}) {
    const f = frame(title, table, caption);
    host.insertAdjacentHTML('beforeend', f.html);
    const fig = host.querySelector(`#${f.id}`);
    plot(fig, {width, height, points, ticks: [0, 50, 100], draw: (svg, {x, y}) => {
      const band = points.length > 1 ? (x(1) - x(0)) : 60;
      const w = Math.min(24, band - 2);
      return points.map((p, i) => {
        if (p.value == null) return null;
        const top = y(p.value), base = y(0), r = Math.min(4, (base - top) / 2);
        const left = x(i) - w / 2;
        const d = `M${left},${base} L${left},${top + r} Q${left},${top} ${left + r},${top} L${left + w - r},${top} `
          + `Q${left + w},${top} ${left + w},${top + r} L${left + w},${base} Z`;
        return el('path', {d, class: 'viz-bar'}, svg);
      });
    }});
  }

  /* Progress bar (meter): same colour, track one lighter step. */
  const meter = (percent, label) => `<div class="viz-meter" role="img" aria-label="${esc(label)}">
    <i style="width:${Math.max(0, Math.min(100, percent || 0))}%"></i></div>`;

  return {line, columns, meter, pct};
})();

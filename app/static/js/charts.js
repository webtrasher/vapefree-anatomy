/* График динамики тяги, настроения и сна. Рисуется в SVG без библиотек. */
(function () {
  'use strict';

  const host = document.querySelector('[data-chart-host]');
  const dataEl = document.querySelector('[data-chart-data]');
  if (!host || !dataEl) return;

  let rows = [];
  try {
    rows = JSON.parse(dataEl.textContent || '[]');
  } catch (error) {
    rows = [];
  }
  if (!rows.length) return;

  const svg = host.querySelector('svg');
  if (!svg) return;

  const W = 720;
  const H = 200;
  const pad = { top: 14, right: 12, bottom: 26, left: 30 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;
  const n = rows.length;

  const NS = 'http://www.w3.org/2000/svg';

  function el(name, attrs, text) {
    const node = document.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach(function (key) {
      node.setAttribute(key, attrs[key]);
    });
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function x(i) {
    return pad.left + (n === 1 ? plotW / 2 : (plotW * i) / (n - 1));
  }

  function yValue(value) {
    // 1..10 -> низ..верх
    const ratio = (Math.max(1, Math.min(10, value)) - 1) / 9;
    return pad.top + plotH - ratio * plotH;
  }

  function ySleep(hours) {
    const ratio = Math.max(0, Math.min(12, hours || 0)) / 12;
    return pad.top + plotH - ratio * plotH * 0.55;
  }

  /* Сетка и подписи оси Y */
  [1, 3, 5, 7, 10].forEach(function (value) {
    const yy = yValue(value);
    svg.appendChild(el('line', { class: 'gridline', x1: pad.left, x2: W - pad.right, y1: yy, y2: yy }));
    svg.appendChild(el('text', { class: 'label', x: 4, y: yy + 3 }, String(value)));
  });

  /* Столбики сна — фоном */
  rows.forEach(function (row, i) {
    if (row.sleep === null || row.sleep === undefined) return;
    const barW = Math.max(3, plotW / n - 4);
    const top = ySleep(row.sleep);
    svg.appendChild(
      el('rect', {
        x: x(i) - barW / 2,
        y: top,
        width: barW,
        height: pad.top + plotH - top,
        rx: 3,
        fill: '#dbe9f2',
        opacity: '0.75',
      })
    );
  });

  /* Подписи оси X (каждые 5 дней) */
  rows.forEach(function (row, i) {
    if (i % 5 !== 0 && i !== n - 1) return;
    svg.appendChild(
      el('text', { class: 'label', x: x(i), y: H - 8, 'text-anchor': 'middle' }, row.label || '')
    );
  });

  /* Базовые линии осей */
  svg.appendChild(
    el('line', { class: 'axis', x1: pad.left, x2: W - pad.right, y1: pad.top + plotH, y2: pad.top + plotH })
  );

  function drawSeries(field, lineClass, dotClass) {
    const segments = [];
    let current = [];

    rows.forEach(function (row, i) {
      const value = row[field];
      if (value === null || value === undefined) {
        if (current.length) segments.push(current);
        current = [];
        return;
      }
      current.push([x(i), yValue(value)]);
      svg.appendChild(el('circle', { class: dotClass, cx: x(i), cy: yValue(value), r: 2.6 }));
    });
    if (current.length) segments.push(current);

    segments.forEach(function (segment) {
      if (segment.length < 2) return;
      const d = segment
        .map(function (point, index) {
          return (index === 0 ? 'M ' : 'L ') + point[0].toFixed(1) + ',' + point[1].toFixed(1);
        })
        .join(' ');
      svg.appendChild(el('path', { class: lineClass, d: d }));
    });
  }

  drawSeries('craving', 'line-craving', 'dot-craving');
  drawSeries('mood', 'line-mood', 'dot-mood');

  /* Доступное текстовое описание графика */
  const filled = rows.filter(function (r) {
    return r.craving !== null && r.craving !== undefined;
  });
  if (filled.length >= 2) {
    const first = filled[0];
    const last = filled[filled.length - 1];
    const delta = last.craving - first.craving;
    const direction = delta === 0 ? 'без изменений' : delta < 0 ? 'снизилась на ' + Math.abs(delta) : 'выросла на ' + delta;
    svg.setAttribute(
      'aria-label',
      'График за ' + rows.length + ' дней. Тяга ' + direction + ' — с ' + first.craving + ' до ' + last.craving + ' из 10.'
    );
  } else {
    svg.setAttribute('aria-label', 'Пока недостаточно данных для графика. Заполните чек-ин.');
  }
})();

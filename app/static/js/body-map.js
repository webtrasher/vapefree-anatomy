/* Анатомическая схема: подсветка органов, фокус, модальные карточки. */
(function () {
  'use strict';

  const stage = document.querySelector('[data-body-stage]');
  const dialog = document.getElementById('organ-dialog');
  const content = document.getElementById('organ-dialog-content');
  if (!stage || !dialog || !content) return;

  const VF = window.VF || {};
  const organGroups = Array.from(stage.querySelectorAll('.organ'));
  const triggerButtons = Array.from(document.querySelectorAll('[data-organ-open]'));
  let lastTrigger = null;

  /* ------------------------------------------------------------------ */
  /* Цвета органов по фазам                                              */
  /* ------------------------------------------------------------------ */
  const PHASE_COLORS = {
    acute: '#c97f7f',
    regeneration: '#d69a63',
    active: '#bfae5f',
    restored: '#6fae90',
  };

  // Начальные проценты из отрисованной страницы -> цвет органа.
  triggerButtons.forEach(function (button) {
    const key = button.dataset.organOpen;
    const percentEl = document.querySelector('[data-organ-percent="' + key + '"]');
    if (!percentEl) return;
    const percent = parseInt(percentEl.textContent, 10) || 0;
    paint(key, percent);
  });

  function colorFor(percent) {
    if (percent >= 65) return PHASE_COLORS.restored;
    if (percent >= 40) return PHASE_COLORS.active;
    if (percent >= 15) return PHASE_COLORS.regeneration;
    return PHASE_COLORS.acute;
  }

  function paint(key, percent) {
    const group = stage.querySelector('.organ[data-organ="' + key + '"]');
    if (group) group.style.setProperty('--organ-color', colorFor(percent));
  }

  /* ------------------------------------------------------------------ */
  /* Загрузка карточки органа                                            */
  /* ------------------------------------------------------------------ */
  function setActive(key) {
    organGroups.forEach(function (group) {
      group.classList.toggle('is-active', group.dataset.organ === key);
    });
    triggerButtons.forEach(function (button) {
      button.setAttribute('aria-current', button.dataset.organOpen === key ? 'true' : 'false');
    });
  }

  function openOrgan(key, trigger) {
    lastTrigger = trigger || null;
    setActive(key);
    content.innerHTML = '<p class="muted">Загрузка…</p>';
    if (typeof VF.openDialog === 'function') VF.openDialog(dialog);
    else dialog.setAttribute('open', '');

    fetch('/organ/' + encodeURIComponent(key) + '/card', {
      headers: { 'X-Requested-With': 'fetch' },
      credentials: 'same-origin',
    })
      .then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.text();
      })
      .then(function (html) {
        content.innerHTML = html;
        const heading = content.querySelector('h2');
        if (heading) {
          heading.id = 'organ-dialog-title';
          heading.setAttribute('tabindex', '-1');
          heading.focus({ preventScroll: true });
        }
      })
      .catch(function () {
        content.innerHTML =
          '<p class="muted">Не удалось загрузить модуль. ' +
          '<a href="/organ/' + encodeURIComponent(key) + '">Открыть отдельной страницей</a>.</p>';
      });
  }

  dialog.addEventListener('close', function () {
    setActive(null);
    if (lastTrigger && typeof lastTrigger.focus === 'function') lastTrigger.focus();
  });

  /* ------------------------------------------------------------------ */
  /* События                                                             */
  /* ------------------------------------------------------------------ */
  organGroups.forEach(function (group) {
    group.addEventListener('click', function () {
      openOrgan(group.dataset.organ, group);
    });
    group.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar') {
        event.preventDefault();
        openOrgan(group.dataset.organ, group);
      }
    });
    group.addEventListener('mouseenter', function () {
      group.classList.add('is-active');
    });
    group.addEventListener('mouseleave', function () {
      if (!dialog.open) group.classList.remove('is-active');
    });
  });

  triggerButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      openOrgan(button.dataset.organOpen, button);
    });
  });

  // Снять анимацию сканирования после проигрывания.
  if (stage.classList.contains('is-scanning')) {
    window.setTimeout(function () {
      stage.classList.remove('is-scanning');
    }, 2600);
  }
})();

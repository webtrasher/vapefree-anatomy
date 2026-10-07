/* VapeFree Anatomy — общий клиентский слой.
   Без внешних зависимостей и CDN: приложение работает офлайн как PWA. */
(function () {
  'use strict';

  const VF = (window.VF = window.VF || {});

  /* ------------------------------------------------------------------ */
  /* Тост-уведомления                                                    */
  /* ------------------------------------------------------------------ */
  const toastEl = document.getElementById('toast');
  let toastTimer = null;

  VF.toast = function (message, ms) {
    if (!toastEl) return;
    toastEl.textContent = message;
    toastEl.classList.add('is-visible');
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      toastEl.classList.remove('is-visible');
    }, ms || 3200);
  };

  /* ------------------------------------------------------------------ */
  /* Service worker (PWA, офлайн-режим)                                  */
  /* ------------------------------------------------------------------ */
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js').catch(function () {
        /* офлайн-режим недоступен — приложение продолжает работать онлайн */
      });
    });
  }

  /* ------------------------------------------------------------------ */
  /* Диалоги                                                             */
  /* ------------------------------------------------------------------ */
  function openDialog(dialog) {
    if (!dialog) return;
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
  }

  function closeDialog(dialog) {
    if (!dialog) return;
    if (typeof dialog.close === 'function') dialog.close();
    else dialog.removeAttribute('open');
  }

  VF.openDialog = openDialog;
  VF.closeDialog = closeDialog;

  // Закрытие по клику вне содержимого
  document.querySelectorAll('dialog').forEach(function (dialog) {
    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) closeDialog(dialog);
    });
  });

  document.addEventListener('click', function (event) {
    const closeBtn = event.target.closest('[data-dialog-close]');
    if (closeBtn) {
      closeDialog(closeBtn.closest('dialog'));
      return;
    }

    const lapseOpen = event.target.closest('[data-lapse-open]');
    if (lapseOpen) {
      openDialog(document.getElementById('lapse-dialog'));
      return;
    }

    const lapseClose = event.target.closest('[data-lapse-close]');
    if (lapseClose) {
      closeDialog(document.getElementById('lapse-dialog'));
    }
  });

  /* ------------------------------------------------------------------ */
  /* Формы с подтверждением                                              */
  /* ------------------------------------------------------------------ */
  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  /* ------------------------------------------------------------------ */
  /* Ползунки: живое значение                                            */
  /* ------------------------------------------------------------------ */
  document.querySelectorAll('input[type="range"][data-range-output]').forEach(function (input) {
    const output = document.getElementById(input.dataset.rangeOutput);
    if (!output) return;
    const sync = function () {
      output.textContent = input.value;
    };
    input.addEventListener('input', sync);
    sync();
  });

  /* ------------------------------------------------------------------ */
  /* Живой таймер + синхронизация состояния                              */
  /* ------------------------------------------------------------------ */
  const dashboard = document.querySelector('[data-dashboard]');

  function split(hours) {
    let total = Math.max(0, Math.floor(hours * 3600));
    const days = Math.floor(total / 86400);
    total -= days * 86400;
    const h = Math.floor(total / 3600);
    total -= h * 3600;
    const m = Math.floor(total / 60);
    return { days: days, hours: h, minutes: m, seconds: total - m * 60 };
  }

  function pad(value, width) {
    return String(value).padStart(width || 2, '0');
  }

  function writeTimer(root, parts) {
    if (!root) return;
    const map = { days: parts.days, hours: pad(parts.hours), minutes: pad(parts.minutes), seconds: pad(parts.seconds) };
    Object.keys(map).forEach(function (unit) {
      const el = root.querySelector('[data-unit="' + unit + '"]');
      if (el) el.textContent = map[unit];
    });
  }

  if (dashboard) {
    const effective0 = parseFloat(dashboard.dataset.effectiveHours || '0');
    const streak0 = parseFloat(dashboard.dataset.streakHours || '0');
    const startedAt = Date.now();

    const streakRoot = dashboard.querySelector('[data-timer="streak"]');
    const timerChip = document.querySelector('[data-timer-chip]');
    const textEl = dashboard.querySelector('[data-timer-text="effective"]');

    function tick() {
      const elapsed = (Date.now() - startedAt) / 3600000;
      const streakHours = streak0 + elapsed;
      writeTimer(streakRoot, split(streakHours));

      if (timerChip) {
        timerChip.hidden = false;
        const wholeDays = Math.floor(streakHours / 24);
        const chipDays = timerChip.querySelector('[data-unit="days"]');
        if (chipDays) chipDays.textContent = wholeDays;
        const unitLabel = timerChip.querySelector('[data-unit="label"]');
        if (unitLabel) {
          const mod10 = wholeDays % 10;
          const mod100 = wholeDays % 100;
          let word = 'дн.';
          if (mod100 < 11 || mod100 > 14) {
            if (mod10 === 1) word = 'день';
            else if (mod10 >= 2 && mod10 <= 4) word = 'дня';
          }
          unitLabel.textContent = word;
        }
      }
    }

    tick();
    window.setInterval(tick, 1000);

    /* Периодическая синхронизация: цвета органов, проценты, фаза. */
    function applyState(state) {
      if (!state || state.authenticated === false) return;

      const overall = document.querySelector('[data-overall-percent]');
      if (overall) overall.textContent = state.overall + '%';

      const ring = document.querySelector('[data-ring-value]');
      if (ring) {
        const circumference = 2 * Math.PI * 52;
        ring.setAttribute('stroke-dashoffset', String(circumference - (circumference * state.overall) / 100));
        ring.setAttribute('stroke', state.phase.color);
      }

      const phaseLabel = document.querySelector('[data-phase-label]');
      if (phaseLabel) phaseLabel.textContent = state.phase.label;

      document.querySelectorAll('[data-organ-percent]').forEach(function (el) {
        const organ = state.organs[el.dataset.organPercent];
        if (organ) el.textContent = organ.percent + '%';
      });

      document.querySelectorAll('[data-organ-bar]').forEach(function (el) {
        const organ = state.organs[el.dataset.organBar];
        if (organ) el.style.width = organ.percent + '%';
      });

      document.querySelectorAll('[data-body-stage] .organ').forEach(function (group) {
        const organ = state.organs[group.dataset.organ];
        if (organ) group.style.setProperty('--organ-color', organ.color);
      });

      if (textEl && state.timers) textEl.textContent = state.timers.effective_text;
    }

    window.VF.applyState = applyState;

    window.setInterval(function () {
      fetch('/api/state', { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
        .then(function (response) {
          return response.ok ? response.json() : null;
        })
        .then(applyState)
        .catch(function () {
          /* офлайн — таймер продолжает идти локально */
        });
    }, 300000);
  }

  /* ------------------------------------------------------------------ */
  /* Системные уведомления                                               */
  /* ------------------------------------------------------------------ */
  const notifBtn = document.querySelector('[data-enable-notifications]');
  const notifStatus = document.querySelector('[data-notification-status]');

  function describePermission(permission) {
    const map = {
      granted: 'Статус: разрешено — напоминания будут приходить, пока приложение открыто.',
      denied: 'Статус: запрещено в настройках браузера.',
      default: 'Статус: не запрошено',
    };
    return map[permission] || 'Статус: неизвестно';
  }

  if (notifBtn) {
    if (notifStatus && 'Notification' in window) {
      notifStatus.textContent = describePermission(Notification.permission);
    }
    notifBtn.addEventListener('click', function () {
      if (!('Notification' in window)) {
        VF.toast('Браузер не поддерживает системные уведомления');
        return;
      }
      Notification.requestPermission().then(function (permission) {
        if (notifStatus) notifStatus.textContent = describePermission(permission);
        if (permission === 'granted') {
          VF.toast('Уведомления разрешены');
          new Notification('VapeFree Anatomy', {
            body: 'Отлично! Будем напоминать о чек-ине и поддерживать на пути.',
            icon: '/static/icons/icon-192.png',
          });
        } else {
          VF.toast('Уведомления не разрешены');
        }
      });
    });
  }
})();

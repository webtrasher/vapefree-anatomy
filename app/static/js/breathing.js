/* Дыхательная практика 4-7-8 со встроенным таймером. */
(function () {
  'use strict';

  const root = document.querySelector('[data-breathing]');
  if (!root) return;

  const orb = root.querySelector('[data-breath-orb]');
  const countEl = root.querySelector('[data-breath-count]');
  const phaseEl = root.querySelector('[data-breath-phase]');
  const startBtn = root.querySelector('[data-breath-start]');
  const stopBtn = root.querySelector('[data-breath-stop]');
  const dots = Array.from(root.querySelectorAll('.cycle-dot'));
  const totalEl = root.querySelector('[data-breathing-total]');

  const PATTERN = { inhale: 4, hold: 7, exhale: 8, cycles: 4 };
  const PHASE_LABEL = { inhale: 'Вдох носом', hold: 'Задержка', exhale: 'Выдох через рот', idle: 'Готовы?' };

  let running = false;
  let timer = null;
  let phase = 'inhale';
  let remaining = PATTERN.inhale;
  let cycle = 0;

  function paintDots() {
    dots.forEach(function (dot, index) {
      dot.classList.toggle('is-done', index < cycle);
    });
  }

  function setPhase(next) {
    phase = next;
    remaining = PATTERN[next];
    orb.dataset.phase = next;
    phaseEl.textContent = PHASE_LABEL[next];
    countEl.textContent = String(remaining);

    // Синхронизируем длительность CSS-перехода с длительностью фазы.
    const seconds = PATTERN[next];
    orb.style.transitionDuration = seconds + 's';
  }

  function advance() {
    if (phase === 'inhale') {
      setPhase('hold');
    } else if (phase === 'hold') {
      setPhase('exhale');
    } else {
      cycle += 1;
      paintDots();
      if (cycle >= PATTERN.cycles) {
        finish();
        return;
      }
      setPhase('inhale');
    }
  }

  function tick() {
    remaining -= 1;
    if (remaining <= 0) {
      advance();
      return;
    }
    countEl.textContent = String(remaining);
  }

  function begin() {
    running = true;
    cycle = 0;
    paintDots();
    startBtn.hidden = true;
    stopBtn.hidden = false;
    setPhase('inhale');
    window.clearInterval(timer);
    timer = window.setInterval(tick, 1000);
  }

  function stop(message) {
    running = false;
    window.clearInterval(timer);
    timer = null;
    startBtn.hidden = false;
    startBtn.textContent = 'Начать снова';
    stopBtn.hidden = true;
    orb.dataset.phase = 'idle';
    orb.style.transitionDuration = '1s';
    phaseEl.textContent = message || 'Остановлено';
    countEl.textContent = '—';
  }

  function finish() {
    window.clearInterval(timer);
    timer = null;
    running = false;
    paintDots();
    startBtn.hidden = false;
    startBtn.textContent = 'Ещё один курс';
    stopBtn.hidden = true;
    orb.dataset.phase = 'idle';
    phaseEl.textContent = 'Курс завершён';
    countEl.textContent = '✓';

    const now = new Date();
    const localDate =
      now.getFullYear() +
      '-' +
      String(now.getMonth() + 1).padStart(2, '0') +
      '-' +
      String(now.getDate()).padStart(2, '0');

    fetch('/api/breathing/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ local_date: localDate }),
    })
      .then(function (response) {
        return response.ok ? response.json() : null;
      })
      .then(function (data) {
        if (data && data.ok) {
          if (totalEl) totalEl.textContent = String(data.breathing_sessions);
          if (window.VF && window.VF.toast) {
            window.VF.toast('Практика засчитана. Тяга должна отступить в ближайшие минуты.');
          }
        }
      })
      .catch(function () {
        if (window.VF && window.VF.toast) {
          window.VF.toast('Не удалось сохранить практику — попробуйте позже.');
        }
      });
  }

  startBtn.addEventListener('click', begin);
  stopBtn.addEventListener('click', function () {
    stop('Остановлено');
  });

  // Пробел запускает и останавливает практику.
  document.addEventListener('keydown', function (event) {
    if (event.code !== 'Space' || event.target.matches('input, textarea, select, button')) return;
    event.preventDefault();
    if (running) stop('Остановлено');
    else begin();
  });

  window.addEventListener('beforeunload', function () {
    window.clearInterval(timer);
  });
})();

/* Онбординг: пошаговая форма, часовой пояс, значение по умолчанию для таймера. */
(function () {
  'use strict';

  const form = document.querySelector('[data-stepper]');
  if (!form) return;

  /* Часовой пояс: getTimezoneOffset() возвращает минуты «назад» от UTC. */
  const offsetField = form.querySelector('[data-tz-offset]');
  if (offsetField) offsetField.value = String(new Date().getTimezoneOffset());

  /* Предзаполнить поле «последняя затяжка». */
  const quitInput = form.querySelector('[name="quit_at_local"]');
  if (quitInput) {
    const pad = function (value) {
      return String(value).padStart(2, '0');
    };
    const toLocalInput = function (date) {
      return (
        date.getFullYear() +
        '-' +
        pad(date.getMonth() + 1) +
        '-' +
        pad(date.getDate()) +
        'T' +
        pad(date.getHours()) +
        ':' +
        pad(date.getMinutes())
      );
    };

    if (quitInput.dataset.defaultUtc) {
      const parsed = new Date(quitInput.dataset.defaultUtc);
      if (!Number.isNaN(parsed.getTime())) quitInput.value = toLocalInput(parsed);
    } else {
      quitInput.value = toLocalInput(new Date());
    }
    quitInput.max = toLocalInput(new Date());
  }

  /* Пошаговая навигация. Без JS все шаги видны — форма остаётся рабочей. */
  const steps = Array.from(form.querySelectorAll('[data-step]'));
  const dots = Array.from(document.querySelectorAll('[data-step-dots] .step-dot'));
  const prevBtn = form.querySelector('[data-step-prev]');
  const nextBtn = form.querySelector('[data-step-next]');
  const submitBtn = form.querySelector('[data-step-submit]');
  const stepField = form.querySelector('[name="step"]');
  let index = 0;

  function render() {
    steps.forEach(function (step, i) {
      const active = i === index;
      step.hidden = !active;
      step.querySelectorAll('input, select, textarea').forEach(function (field) {
        field.disabled = !active;
      });
    });
    dots.forEach(function (dot, i) {
      dot.classList.toggle('is-active', i <= index);
    });
    if (prevBtn) prevBtn.hidden = index === 0;
    if (nextBtn) nextBtn.hidden = index === steps.length - 1;
    if (submitBtn) submitBtn.hidden = index !== steps.length - 1;
    if (stepField) stepField.value = String(index + 1);
  }

  function validateCurrent() {
    const step = steps[index];
    if (!step) return true;
    const required = Array.from(step.querySelectorAll('[required]'));
    for (const field of required) {
      if (!field.value || !field.checkValidity()) {
        field.reportValidity();
        field.focus();
        return false;
      }
    }
    return true;
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', function () {
      if (!validateCurrent()) return;
      index = Math.min(index + 1, steps.length - 1);
      render();
      const heading = steps[index].querySelector('legend');
      if (heading) heading.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener('click', function () {
      index = Math.max(index - 1, 0);
      render();
    });
  }

  form.addEventListener('submit', function (event) {
    // Финальная проверка: включить все поля, иначе браузер их не отправит.
    steps.forEach(function (step) {
      step.querySelectorAll('input, select, textarea').forEach(function (field) {
        field.disabled = false;
      });
    });
    if (!form.checkValidity()) {
      event.preventDefault();
      const invalid = form.querySelector(':invalid');
      if (invalid) {
        const parentStep = invalid.closest('[data-step]');
        if (parentStep) {
          index = steps.indexOf(parentStep);
          render();
        }
        invalid.reportValidity();
      }
    }
  });

  render();
})();

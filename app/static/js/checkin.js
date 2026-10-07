/* Чек-ин: дата определяется по локальным часам пользователя. */
(function () {
  'use strict';

  const root = document.querySelector('[data-checkin]');
  if (!root) return;

  const input = root.querySelector('[data-local-date]');
  if (!input) return;

  const now = new Date();
  const localDate =
    now.getFullYear() +
    '-' +
    String(now.getMonth() + 1).padStart(2, '0') +
    '-' +
    String(now.getDate()).padStart(2, '0');

  input.value = localDate;
})();

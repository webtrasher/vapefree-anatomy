/* VapeFree Anatomy — service worker.
   Стратегия: static — cache-first, навигация — network-first с откатом в кэш. */

const VERSION = 'vapefree-v1';
const STATIC_CACHE = VERSION + '-static';
const PAGE_CACHE = VERSION + '-pages';

const PRECACHE = [
  '/',
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/js/body-map.js',
  '/static/js/charts.js',
  '/static/js/breathing.js',
  '/static/js/checkin.js',
  '/static/js/onboarding.js',
  '/static/img/body-map.svg',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/manifest.webmanifest',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE).catch(() => undefined))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => !key.startsWith(VERSION))
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  // Не кэшируем API: таймер и проценты должны быть актуальными.
  if (url.pathname.startsWith('/api/')) return;

  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.webmanifest') {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            const copy = response.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
            return response;
          })
      )
    );
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(PAGE_CACHE).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() =>
          caches.match(request).then(
            (cached) =>
              cached ||
              new Response(
                '<!doctype html><html lang="ru"><meta charset="utf-8">' +
                  '<meta name="viewport" content="width=device-width,initial-scale=1">' +
                  '<title>Нет соединения</title>' +
                  '<body style="font-family:system-ui;padding:2rem;background:#f6fafb;color:#22313a">' +
                  '<h1>Нет соединения</h1>' +
                  '<p>Страница ещё не сохранена для офлайн-режима. Дашборд, чек-ин и дыхание ' +
                  'доступны из кэша после первого открытия.</p>' +
                  '<p><a href="/dashboard">Попробовать дашборд</a></p></body></html>',
                { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
              )
          )
        )
    );
  }
});

/* Локальные напоминания, инициированные страницей. */
self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.type === 'notify' && data.title) {
    self.registration.showNotification(data.title, {
      body: data.body || '',
      icon: '/static/icons/icon-192.png',
      badge: '/static/icons/icon-192.png',
      tag: data.tag || 'vapefree',
      lang: 'ru',
    });
  }
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow('/dashboard'));
});

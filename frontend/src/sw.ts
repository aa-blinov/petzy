/// <reference lib="webworker" />
export {}

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: Array<{ url: string; revision: string | null }> }

import { precacheAndRoute, createHandlerBoundToURL } from 'workbox-precaching'
import { registerRoute, NavigationRoute } from 'workbox-routing'
import { NetworkOnly } from 'workbox-strategies'

self.skipWaiting()

precacheAndRoute(self.__WB_MANIFEST)

// Vite emits <link rel="modulepreload" crossorigin> for every vendor
// chunk. Workbox's navigation-fallback handler intercepts those as
// navigations and throws "cross-origin service worker resource
// mismatch" in the console — the preloads become dead weight. Keep
// Workbox's hands off hashed asset bundles; the browser's HTTP cache
// + Workbox precache handle them just fine.
registerRoute(
  new NavigationRoute(createHandlerBoundToURL('index.html'), {
    denylist: [/^\/assets\//],
  })
)

// No API response is ever served from a cache.
//
// This used to be NetworkFirst with a 60-second TTL (and /api/pets was
// CacheFirst for five minutes). Both were a bad trade for a health
// diary: a one-minute window buys essentially no offline capability —
// anything longer than a minute offline and the cache is stale anyway
// — while it did leave one user's pet roster and medical records in
// Cache Storage on a possibly shared device, ready to be served to
// whoever signed in next, and let a slow backend (mid-deploy) answer
// from a stale entry so the UI rendered old data and then corrected
// itself.
//
// It matters most for /auth/session, the app's "am I signed in?"
// probe: a cached 200 there would keep a signed-out user looking
// signed in, and it has to fail loudly during a deploy rather than
// answer from a stale entry.
//
// The app shell is still precached, so the PWA installs and launches
// offline; data simply requires the network and says so when missing.
registerRoute(/^\/api\/.*/i, new NetworkOnly(), 'GET')

// --- Push notifications -----------------------------------------------
//
// The backend (scripts/send_medication_reminders.py) sends a JSON
// payload — {title, body, url} — for each dose that just became due.
// Showing it is the service worker's job specifically because it has
// to work while the app itself isn't open; that's the entire point of
// push over an in-app reminder.
self.addEventListener('push', (event: PushEvent) => {
  let data: { title?: string; body?: string; url?: string } = {}
  try {
    data = event.data?.json() ?? {}
  } catch {
    // Malformed or empty payload — still show *something* rather than
    // silently drop a notification the user is expecting.
  }

  event.waitUntil(
    self.registration.showNotification(data.title ?? 'Petzy', {
      body: data.body,
      // PNG: notification icons don't reliably render SVG. The badge is a
      // white silhouette on transparent, which Android tints itself.
      icon: '/icon-192.png',
      badge: '/badge-96.png',
      data: { url: data.url ?? '/' },
    })
  )
})

// v1: clicking the notification just opens/focuses the app (the
// Лента tab already surfaces a "Принять сейчас" widget for the exact
// dose the notification was about). Acting on the dose straight from
// the notification's own action buttons — no need to open the app at
// all — is a natural next step: the SPA authenticates via an httpOnly
// cookie (see api.ts's withCredentials), so a fetch from here would
// carry it automatically. Left for later rather than blocking v1 on it.
self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close()
  const url = (event.notification.data?.url as string) ?? '/'

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      const existing = clients.find((c) => c.url.startsWith(self.location.origin))
      if (existing) return existing.focus()
      return self.clients.openWindow(url)
    })
  )
})

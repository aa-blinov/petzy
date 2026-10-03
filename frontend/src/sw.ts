/// <reference lib="webworker" />
export {}

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: Array<{ url: string; revision: string | null }> }

import { precacheAndRoute, createHandlerBoundToURL } from 'workbox-precaching'
import { registerRoute, NavigationRoute } from 'workbox-routing'
import { CacheFirst, NetworkOnly } from 'workbox-strategies'
import { clientsClaim } from 'workbox-core'

// A new release takes over open pages at once (see utils/swUpdate.ts,
// which reloads them into it where that's safe).
self.skipWaiting()
clientsClaim()

precacheAndRoute(self.__WB_MANIFEST)

// Vite emits <link rel="modulepreload" crossorigin> for every vendor
// chunk. Workbox's navigation-fallback handler intercepts those as
// navigations and throws "cross-origin service worker resource
// mismatch" in the console — the preloads become dead weight. Keep
// Workbox's hands off hashed asset bundles; the browser's HTTP cache
// + Workbox precache handle them just fine.
//
// /api/ too: opening a document (the PDF viewer's iframe, a scan
// download that redirects to the bucket) is a navigation, and answering
// it with index.html shows the app inside the viewer instead of the file.
registerRoute(
  new NavigationRoute(createHandlerBoundToURL('index.html'), {
    denylist: [/^\/assets\//, /^\/api\//],
  })
)

// The pets' hand-written faces are left out of the precache (vite.config.ts): the first time one is used it is fetched, and
// from then on it is served from here, so a name keeps its face offline.
registerRoute(
  ({ url }) => /^\/assets\/(caveat|marck-script|bad-script|pacifico|neucha|amatic-sc)-.*\.woff2$/.test(url.pathname),
  new CacheFirst({ cacheName: 'pet-fonts' })
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
  let data: { title?: string; body?: string; url?: string; tag?: string } = {}
  try {
    data = event.data?.json() ?? {}
  } catch {
    // Malformed or empty payload — still show *something* rather than
    // silently drop a notification the user is expecting.
  }

  event.waitUntil(
    self.registration.showNotification(data.title ?? 'Petzy', {
      body: data.body,
      // The same dose reaching one phone twice (two subscriptions of one person) is one notification, not two.
      tag: data.tag,
      // PNG: notification icons don't reliably render SVG. The badge is a
      // white silhouette on transparent, which Android tints itself.
      icon: '/icon-192.png',
      badge: '/badge-96.png',
      data: { url: data.url ?? '/' },
    })
  )
})

// Clicking the notification takes you to the page it is about: a reminder
// for a vaccination opens that pet's medical card, a dose the feed. The app
// being open already used to be no reason to stay where it was (the click
// only focused the window and ignored the link), and a link without the pet
// in it could open another pet's page, so links carry the pet where it
// matters (/pets/<id>/medical-card).
//
// Acting on a dose straight from the notification's own buttons is a natural
// next step: the SPA authenticates via an httpOnly cookie (see api.ts's
// withCredentials), so a fetch from here would carry it automatically.
self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close()
  const target = new URL((event.notification.data?.url as string) ?? '/', self.location.origin).href

  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      const existing = windows.find((c) => c.url.startsWith(self.location.origin))
      if (!existing) return self.clients.openWindow(target)
      // navigate() only works for a window this worker controls; if it refuses
      // (an uncontrolled tab), open the link in a window of its own rather than
      // leave the click without a result.
      let page: WindowClient = existing
      try {
        page = (await existing.navigate(target)) ?? existing
      } catch {
        return self.clients.openWindow(target)
      }
      // Bringing it forward is allowed inside a real click; if a browser still
      // refuses, the page is on the right address all the same, and a second
      // window would only be in the way.
      try {
        return await page.focus()
      } catch {
        return page
      }
    })()
  )
})

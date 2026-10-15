/**
 * Brings a new release to an app that stays open. The browser only looks
 * for a new service worker on a navigation, and an installed app resumed
 * from the background doesn't navigate: a phone kept running a build from
 * days before. So the app asks when it comes back to the screen and every
 * hour; the new worker takes over at once (skipWaiting + clientsClaim in
 * sw.ts), and the person is offered «Обновить» (components/UpdateBanner.tsx)
 * instead of a reload that came on its own: a form half filled in is never
 * lost to it, and nobody has to reinstall the app to get a new version.
 */
let updateReady = false;
const listeners = new Set<() => void>();

export function isUpdateReady(): boolean {
  return updateReady;
}

export function subscribeUpdate(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function watchForUpdates(): void {
  if (!('serviceWorker' in navigator)) return;
  // The very first install also takes control; that isn't an update.
  const hadController = !!navigator.serviceWorker.controller;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (!hadController || updateReady) return;
    updateReady = true;
    listeners.forEach((listener) => listener());
  });

  const check = () => {
    navigator.serviceWorker
      .getRegistration()
      .then((registration) => registration?.update())
      .catch(() => undefined);
  };
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') check();
  });
  window.setInterval(check, 60 * 60 * 1000);
}

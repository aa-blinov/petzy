import { isMainTabPath } from './navigation';

/**
 * Brings a new release to an app that stays open. The browser only looks
 * for a new service worker on a navigation, and an installed app resumed
 * from the background doesn't navigate: a phone kept running a build from
 * days before. So the app asks when it comes back to the screen and every
 * hour; the new worker takes over at once (skipWaiting + clientsClaim in
 * sw.ts), and the page reloads into it on a main tab, never in the middle
 * of a form someone is filling in.
 */
let updateReady = false;

function onMainTab(pathname: string): boolean {
  return isMainTabPath(pathname);
}

/** Reload into the new release if one is waiting and nothing can be lost here. */
export function reloadIfUpdated(pathname: string): void {
  if (updateReady && onMainTab(pathname)) window.location.reload();
}

export function watchForUpdates(): void {
  if (!('serviceWorker' in navigator)) return;
  // The very first install also takes control; that isn't an update.
  const hadController = !!navigator.serviceWorker.controller;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (!hadController) return;
    updateReady = true;
    reloadIfUpdated(window.location.pathname);
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

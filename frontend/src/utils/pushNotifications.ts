import { pushService } from '../services/push.service';

export type PushSupportState = 'unsupported' | 'denied' | 'off' | 'on';

/** Web Push's own applicationServerKey wants the VAPID public key as a
 *  Uint8Array, not the base64url string the backend hands out — the
 *  standard conversion every Web Push tutorial reaches for. */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function isPushSupported(): boolean {
  return typeof navigator !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window;
}

/** iPhone/iPad Safari (iOS 16.4+) only gives Web Push to a site added to
 *  the Home Screen; in a plain Safari tab PushManager is simply missing,
 *  so push looks "unsupported" when one step would enable it. */
export function needsHomeScreenForPush(): boolean {
  if (typeof navigator === 'undefined' || isPushSupported()) return false;
  const ua = navigator.userAgent;
  const isIos = /iP(hone|od|ad)/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  if (!isIos) return false;
  const standalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
  if (standalone) return false;
  const version = ua.match(/OS (\d+)_(\d+)/);
  // Desktop-class iPad Safari reports a Mac UA without an OS version;
  // those run iPadOS 13+, so assume a current one.
  if (!version) return true;
  const [major, minor] = [Number(version[1]), Number(version[2])];
  return major > 16 || (major === 16 && minor >= 4);
}

/** Current state for the Settings toggle — doesn't touch the network
 *  beyond what the browser itself already knows (no VAPID-key fetch),
 *  so it's cheap enough to call on every mount. */
export async function getPushSubscriptionState(): Promise<PushSupportState> {
  if (!isPushSupported()) return 'unsupported';
  if (Notification.permission === 'denied') return 'denied';

  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  return subscription ? 'on' : 'off';
}

/** Requests permission (if not already decided), subscribes this
 *  browser to push, and registers the subscription with the backend.
 *  Throws with a message suitable for a toast on any failure —
 *  including the server having no VAPID keys configured, which the
 *  caller can't distinguish from a transient error without this. */
export async function subscribeToPush(): Promise<void> {
  if (!isPushSupported()) {
    throw new Error('Этот браузер не поддерживает push-уведомления');
  }

  if (Notification.permission === 'denied') {
    throw new Error('Уведомления заблокированы в настройках браузера');
  }

  const permission = Notification.permission === 'granted' ? 'granted' : await Notification.requestPermission();
  if (permission !== 'granted') {
    throw new Error('Уведомления не разрешены');
  }

  const publicKey = await pushService.getVapidPublicKey();

  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    // TS's DOM lib types Uint8Array's .buffer as ArrayBufferLike (which
    // includes SharedArrayBuffer), while BufferSource wants a concrete
    // ArrayBuffer — a real Uint8Array satisfies the browser's actual
    // API just fine, this is purely a lib-types mismatch.
    applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
  });

  const json = subscription.toJSON();
  if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
    throw new Error('Браузер вернул неполные данные подписки');
  }

  await pushService.subscribe({
    endpoint: json.endpoint,
    keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  });
}

/** Unsubscribes this browser and removes the subscription from the
 *  backend. A no-op (not an error) when there was nothing to remove —
 *  the end state is identical either way. */
export async function unsubscribeFromPush(): Promise<void> {
  if (!isPushSupported()) return;

  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (!subscription) return;

  const endpoint = subscription.endpoint;
  await subscription.unsubscribe();
  await pushService.unsubscribe(endpoint);
}

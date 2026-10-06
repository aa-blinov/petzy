/** What a person had typed into a form when their session ran out.
 *
 *  The app signs a person out by moving to /login, which drops the form with whatever was typed in it. A form that
 *  holds typed-in data registers a provider here while it is dirty; on a session expiry the provider's values are
 *  put in sessionStorage under the address of the screen, and the same screen takes them back once the person has
 *  signed in again. Only an expiry writes a draft, so a form that was left on purpose never comes back. */
const KEY = 'petzy:sessionDraft';

type Provider = () => unknown;
const providers = new Set<Provider>();

export function registerDraftProvider(provider: Provider): () => void {
  providers.add(provider);
  return () => {
    providers.delete(provider);
  };
}

/** Called by the sign-out path before it navigates. */
export function stashDraftsBeforeSignOut(): void {
  for (const provider of providers) {
    const values = provider();
    if (values === undefined) continue;
    try {
      // Только путь, без адреса целиком: черновик принадлежит экрану, а не его строке запроса.
      // Раньше адрес с параметром (например ?returnTo= после истёкшей сессии) не совпадал при возврате,
      // и набранное терялось.
      sessionStorage.setItem(KEY, JSON.stringify({ path: window.location.pathname, values }));
    } catch {
      /* sessionStorage may be unavailable: the form is then lost as before */
    }
    return;
  }
}

/** The draft for the current screen, once: reading it takes it away. */
export function takeDraft<T>(): T | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const draft = JSON.parse(raw) as { path?: string; values?: T };
    // Старый черновик мог быть записан с адресом целиком: сверяем только путь, чтобы он не потерялся.
    const path = (draft.path ?? '').split('?')[0];
    if (path !== window.location.pathname || !draft.values) return null;
    sessionStorage.removeItem(KEY);
    return draft.values;
  } catch {
    return null;
  }
}

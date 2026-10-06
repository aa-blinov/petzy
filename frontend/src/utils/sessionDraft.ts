/** What a person had typed into a form when their session ran out.
 *
 *  The app signs a person out by moving to /login, which drops the form with whatever was typed in it. A form that
 *  holds typed-in data registers a provider here while it is dirty; on a session expiry the provider's values are
 *  put in sessionStorage under the owner of what was written, and the same form takes them back once the person has
 *  signed in again. Only an expiry writes a draft, so a form that was left on purpose never comes back.
 *
 *  The owner is the screen plus the pet it was written for, not the screen alone. Two pets have two of the same
 *  forms open for them, and «вес 12,4» written for one of them is not the answer about the other: a form for a pet
 *  that has not loaded yet owns no draft, so nothing is written and nothing is taken.
 *
 *  Earlier versions kept one draft under `petzy:sessionDraft`, addressed by the path of the screen. It is adopted
 *  into the new store the first time its own screen opens, so a person with an unfinished form does not lose it when
 *  the new code is served; nothing to migrate on the server, because the draft never lived there. */
const KEY = 'petzy:sessionDrafts';
const LEGACY_KEY = 'petzy:sessionDraft';
/** A draft older than this is not what anyone is coming back to: a session lasts days at most, and a tab that
 *  lives for days should not hand back yesterday's numbers as if they were written now. */
const STALE_MS = 12 * 60 * 60 * 1000;

/** What a draft belongs to: the screen it was written on, and the pet it was about. */
export interface DraftOwner {
  path: string;
  petId: string | null;
}

interface Draft {
  path: string;
  petId: string | null;
  values: unknown;
  savedAt: number;
}

type Store = Record<string, Draft>;

type Provider = () => { owner: DraftOwner; values: unknown } | undefined;
const providers = new Set<Provider>();

export function registerDraftProvider(provider: Provider): () => void {
  providers.add(provider);
  return () => {
    providers.delete(provider);
  };
}

function keyOf(owner: DraftOwner): string {
  return `${owner.petId ?? 'без питомца'} ${owner.path}`;
}

function read(): Store {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Store;
    if (!parsed || typeof parsed !== 'object') return {};
    const now = Date.now();
    // Черновик, которому больше суток, не предлагается: иначе давно закрытая вкладка
    // подсовывает числа, будто их только что ввели.
    return Object.fromEntries(Object.entries(parsed).filter(([, d]) => typeof d?.savedAt === 'number' && now - d.savedAt < STALE_MS));
  } catch {
    return {};
  }
}

function write(store: Store): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(store));
  } catch {
    /* sessionStorage may be unavailable: the form is then lost as before */
  }
}

/** Takes the draft of earlier versions into the new store, once, when its own screen opens.
 *
 *  The old entry was addressed by the path and knew nothing about the pet, so it can only be adopted by the screen
 *  that matches it. Another screen leaves it alone rather than guessing who it belonged to. */
function adoptLegacy(owner: DraftOwner): void {
  let raw: string | null;
  try {
    raw = sessionStorage.getItem(LEGACY_KEY);
  } catch {
    return;
  }
  if (!raw) return;
  try {
    const legacy = JSON.parse(raw) as { path?: string; values?: unknown };
    const path = (legacy.path ?? '').split('?')[0];
    if (path !== owner.path || !legacy.values) return;
    const store = read();
    store[keyOf(owner)] = { path: owner.path, petId: owner.petId, values: legacy.values, savedAt: Date.now() };
    write(store);
    sessionStorage.removeItem(LEGACY_KEY);
  } catch {
    /* a draft we cannot read is a draft we drop */
  }
}

/** Called by the sign-out path before it navigates. */
export function stashDraftsBeforeSignOut(): void {
  for (const provider of providers) {
    const given = provider();
    if (!given) continue;
    try {
      adoptLegacy(given.owner);
      const store = read();
      store[keyOf(given.owner)] = {
        path: given.owner.path,
        petId: given.owner.petId,
        values: given.values,
        savedAt: Date.now(),
      };
      write(store);
      // Черновик прежней версии на этом же экране теперь позади, иначе вернётся следом.
      try {
        sessionStorage.removeItem(LEGACY_KEY);
      } catch {
        /* nothing to remove */
      }
    } catch {
      /* sessionStorage may be unavailable: the form is then lost as before */
    }
    return;
  }
}

/** The draft for this owner, once: reading it takes it away. */
export function takeDraft<T>(owner: DraftOwner): T | null {
  try {
    adoptLegacy(owner);
    const store = read();
    const draft = store[keyOf(owner)];
    if (!draft?.values) return null;
    delete store[keyOf(owner)];
    write(store);
    return draft.values as T;
  } catch {
    return null;
  }
}
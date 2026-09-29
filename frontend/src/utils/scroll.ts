/**
 * Scroll position across screens.
 *
 * The router swaps the page but nothing moved the window, so a new screen
 * opened wherever the last one had been scrolled (or, by luck, at the top,
 * when its loading spinner was too short to keep the position). The rules
 * of a mobile app:
 *
 *   - a screen opened by a tap starts at the top;
 *   - «назад» (button, edge swipe, browser) returns to where the user was;
 *   - tapping the tab you are already on scrolls it to the top.
 *
 * Positions are kept per history entry (react-router's `location.key`) in
 * sessionStorage, so a reload comes back to the same place too.
 */

const STORAGE_KEY = 'petzy:scroll';
const MAX_ENTRIES = 60;
/** How long to wait for a lazy, data-driven page to grow tall enough. */
const RESTORE_GIVE_UP_MS = 2500;

type Positions = Record<string, { y: number; path: string }>;

function read(): Positions {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}') as Positions;
  } catch {
    return {};
  }
}

function write(positions: Positions) {
  try {
    const keys = Object.keys(positions);
    // Insertion order is age: forget the oldest entries.
    const kept = keys.length > MAX_ENTRIES ? keys.slice(keys.length - MAX_ENTRIES) : keys;
    const trimmed: Positions = {};
    for (const key of kept) trimmed[key] = positions[key];
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch {
    /* private mode or full storage: positions just aren't remembered */
  }
}

export function savePosition(key: string, y: number, path: string) {
  const positions = read();
  delete positions[key];
  positions[key] = { y: Math.round(y), path };
  write(positions);
}

/** The place this history entry was left at, if it is still the same page:
    every fresh load starts at the key «default», so a typed-in address in
    the same tab mustn't inherit an older page's position. */
export function savedPosition(key: string, path: string): number | null {
  const saved = read()[key];
  return saved && saved.path === path && saved.y > 0 ? saved.y : null;
}

export function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
}

/** Straight to the top, before the new screen is painted. */
export function jumpToTop() {
  window.scrollTo({ top: 0, left: 0, behavior: 'instant' as ScrollBehavior });
}

/** The «tap the current tab again» scroll: smooth, unless motion is off. */
export function scrollToTop() {
  window.scrollTo({ top: 0, left: 0, behavior: prefersReducedMotion() ? ('instant' as ScrollBehavior) : 'smooth' });
}

/**
 * Scroll to `y` once the page is tall enough to reach it (a lazy screen and
 * its data arrive after the route changes). Gives up quietly after a moment,
 * and stops the instant the user touches, wheels or types: their own scroll
 * always wins. Returns a function that cancels it.
 */
export function restorePosition(y: number): () => void {
  let done = false;
  const started = performance.now();
  let frame = 0;

  const stop = () => {
    if (done) return;
    done = true;
    cancelAnimationFrame(frame);
    window.removeEventListener('touchstart', stop);
    window.removeEventListener('wheel', stop);
    window.removeEventListener('keydown', stop);
  };
  window.addEventListener('touchstart', stop, { passive: true });
  window.addEventListener('wheel', stop, { passive: true });
  window.addEventListener('keydown', stop);

  const step = () => {
    if (done) return;
    const reachable = document.documentElement.scrollHeight - window.innerHeight;
    if (reachable >= y - 1) {
      window.scrollTo({ top: y, left: 0, behavior: 'instant' as ScrollBehavior });
      stop();
    } else if (performance.now() - started > RESTORE_GIVE_UP_MS) {
      window.scrollTo({ top: Math.max(0, reachable), left: 0, behavior: 'instant' as ScrollBehavior });
      stop();
    } else {
      frame = requestAnimationFrame(step);
    }
  };
  frame = requestAnimationFrame(step);
  return stop;
}

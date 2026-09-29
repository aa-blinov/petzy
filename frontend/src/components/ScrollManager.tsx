import { useEffect, useLayoutEffect, useRef } from 'react';
import { useLocation, useNavigationType } from 'react-router-dom';
import { jumpToTop, restorePosition, savedPosition, savePosition } from '../utils/scroll';

/**
 * Where each screen starts (see utils/scroll.ts for the rules).
 *
 * A screen reached by a tap, a redirect or a replace opens at the top;
 * one reached by going back or forward gets its old position back. The
 * browser's own restoration is switched off: it runs before a lazy page
 * has any height and lands nowhere.
 */
export function ScrollManager() {
  const location = useLocation();
  const navigationType = useNavigationType();
  // The history entry on screen, and the newest scroll position it had.
  const entryKey = useRef(location.key);
  const latestY = useRef(0);
  const lastPath = useRef<string | null>(null);
  const currentPath = useRef(location.pathname);
  const cancelRestore = useRef<() => void>(() => undefined);

  useEffect(() => {
    const previous = window.history.scrollRestoration;
    window.history.scrollRestoration = 'manual';

    let frame = 0;
    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        latestY.current = window.scrollY;
      });
    };
    // Written when the page is hidden too (a reload, the app going to the
    // background), so coming back lands in the same place.
    const flush = () => savePosition(entryKey.current, window.scrollY, currentPath.current);
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') flush();
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('pagehide', flush);
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('pagehide', flush);
      document.removeEventListener('visibilitychange', onVisibility);
      cancelAnimationFrame(frame);
      window.history.scrollRestoration = previous;
    };
  }, []);

  // Before paint: the screen being left keeps its position, the new one is placed.
  useLayoutEffect(() => {
    cancelRestore.current();

    const first = lastPath.current === null;
    if (!first && entryKey.current !== location.key) savePosition(entryKey.current, latestY.current, currentPath.current);
    currentPath.current = location.pathname;
    entryKey.current = location.key;

    const samePage = lastPath.current === location.pathname;
    lastPath.current = location.pathname;

    if (navigationType === 'POP') {
      const y = savedPosition(location.key, location.pathname);
      if (y !== null) cancelRestore.current = restorePosition(y);
      else if (!first) jumpToTop();
    } else if (!samePage) {
      jumpToTop();
    }
    latestY.current = window.scrollY;
  }, [location.key, location.pathname, navigationType]);

  return null;
}

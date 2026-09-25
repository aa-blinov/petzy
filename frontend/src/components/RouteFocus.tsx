import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Page title and focus on navigation.
 *
 * A single-page app swaps content without a page load, so a screen
 * reader heard nothing when a tab changed, focus stayed on the link
 * that had just been pressed (or on nothing at all), and every tab in
 * the browser read "Petzy". After each route change this waits for the
 * new page's h1 (pages are lazy, so it may arrive a moment later),
 * names the document after it and moves focus there. The first render
 * only sets the title: on a fresh load focus belongs at the top.
 */
export function RouteFocus() {
  const { pathname } = useLocation();
  const isFirstRender = useRef(true);

  useEffect(() => {
    const main = document.getElementById('main-content');
    if (!main) return;
    const moveFocus = !isFirstRender.current;
    isFirstRender.current = false;

    const settle = () => {
      const heading = main.querySelector('h1');
      if (!heading) return false;
      const text = heading.textContent?.trim();
      document.title = text && text !== 'Petzy' ? `${text} · Petzy` : 'Petzy';
      const active = document.activeElement;
      // A page that focused its own field (onboarding's name input) keeps it.
      const pageTookFocus = active instanceof HTMLElement && active !== main && main.contains(active);
      if (moveFocus && !pageTookFocus) {
        heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: true });
      }
      return true;
    };

    if (settle()) return;
    const observer = new MutationObserver(() => {
      if (settle()) observer.disconnect();
    });
    observer.observe(main, { childList: true, subtree: true });
    const timeout = setTimeout(() => observer.disconnect(), 5000);
    return () => {
      observer.disconnect();
      clearTimeout(timeout);
    };
  }, [pathname]);

  return null;
}

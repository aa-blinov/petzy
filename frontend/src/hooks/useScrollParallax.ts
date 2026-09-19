/**
 * Returns a transform string that translates the element by a
 * fraction of the page's scroll position. Used to give the hero
 * photo on the dashboard a subtle parallax as the user scrolls.
 *
 * The factor is intentionally small (0.15) — a tiny vertical shift
 * reads as depth without making the hero feel detached from the
 * card body.
 */

import { useEffect, useState } from 'react';

export function useScrollParallax(factor: number = 0.15) {
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    let raf: number | null = null;
    function onScroll() {
      if (raf != null) return;
      raf = requestAnimationFrame(() => {
        setOffset(window.scrollY * factor);
        raf = null;
      });
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      if (raf != null) cancelAnimationFrame(raf);
    };
  }, [factor]);

  return `translate3d(0, ${offset.toFixed(1)}px, 0)`;
}

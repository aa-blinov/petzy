import { useEffect, useState } from 'react';

/** Reading down a page, the round «+» steps aside, so that it does not stand over a link at the edge; any scroll up, the top
    of the page or a key brings it back. */
export function useFabAway(): boolean {
  const [away, setAway] = useState(false);
  useEffect(() => {
    let last = window.scrollY;
    const onScroll = () => {
      const y = window.scrollY;
      const delta = y - last;
      if (y <= 80 || delta < -8) setAway(false);
      else if (delta > 8) setAway(true);
      last = y;
    };
    const onKey = () => setAway(false);
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('keydown', onKey);
    };
  }, []);
  return away;
}

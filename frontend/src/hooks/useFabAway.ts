import { useEffect, useState } from 'react';

/** Reading down a page, the round «+» steps aside, so that it does not stand over a link at the edge; any scroll up, or a key,
    brings it back. `awayAtTop`: at the top of the page it stays aside as well, for a screen whose top is a grid the button
    would cover (the medical card's last tile); a scroll up off the top still brings it back. */
export function useFabAway(awayAtTop = false): boolean {
  const [away, setAway] = useState(awayAtTop);
  useEffect(() => {
    let last = window.scrollY;
    const onScroll = () => {
      const y = window.scrollY;
      const delta = y - last;
      if (y <= 80) setAway(awayAtTop);
      else if (delta < -8) setAway(false);
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
  }, [awayAtTop]);
  return away;
}

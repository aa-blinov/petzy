/**
 * Detect a horizontal swipe from the left edge of the screen and
 * call navigate(-1). A bare-bones iOS-style back gesture — no fancy
 * preview animation, the route transition already handles the visual
 * part.
 *
 * Only fires for swipes that:
 *  - start in the left 24px edge,
 *  - travel at least 80px right,
 *  - complete within 300ms (fast flick, not a slow scroll).
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const EDGE_PX = 24;
const MIN_TRAVEL = 80;
const MAX_DURATION = 300;

export function useSwipeBack() {
  const navigate = useNavigate();

  useEffect(() => {
    let startX = 0;
    let startY = 0;
    let startTime = 0;
    let tracking = false;

    function onTouchStart(e: TouchEvent) {
      const t = e.touches[0];
      if (t.clientX <= EDGE_PX) {
        startX = t.clientX;
        startY = t.clientY;
        startTime = Date.now();
        tracking = true;
      }
    }

    function onTouchEnd(e: TouchEvent) {
      if (!tracking) return;
      tracking = false;
      const t = e.changedTouches[0];
      const dx = t.clientX - startX;
      const dy = t.clientY - startY;
      const dt = Date.now() - startTime;
      // Must be a horizontal right-swipe, not a vertical scroll.
      if (dx >= MIN_TRAVEL && Math.abs(dy) < 60 && dt <= MAX_DURATION) {
        navigate(-1);
      }
    }

    function onTouchCancel() {
      tracking = false;
    }

    document.addEventListener('touchstart', onTouchStart, { passive: true });
    document.addEventListener('touchend', onTouchEnd, { passive: true });
    document.addEventListener('touchcancel', onTouchCancel, { passive: true });
    return () => {
      document.removeEventListener('touchstart', onTouchStart);
      document.removeEventListener('touchend', onTouchEnd);
      document.removeEventListener('touchcancel', onTouchCancel);
    };
  }, [navigate]);
}

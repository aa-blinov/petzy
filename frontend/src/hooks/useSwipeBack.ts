/**
 * Detect a horizontal swipe from the left edge of the screen and
 * go back one page of this app (see hasPreviousAppPage). A bare-bones iOS-style back gesture — no fancy
 * preview animation, the route transition already handles the visual
 * part.
 *
 * Only fires for swipes that:
 *  - start in the left 24px edge,
 *  - travel at least 80px right,
 *  - complete within 300ms (fast flick, not a slow scroll),
 *  - are clearly horizontal (the sideways travel is at least twice the vertical),
 *  - are made with one finger,
 *  - did not begin on something that owns a sideways drag of its own: a
 *    swipeable row, a field, an open sheet or dialog, a block that scrolls
 *    sideways. Those flicks used to go back a screen nobody asked to leave.
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { hasPreviousAppPage } from '../utils/navigation';

const EDGE_PX = 24;
const MIN_TRAVEL = 80;
const MAX_DURATION = 300;

// Where a sideways drag belongs to the thing under the finger, not to navigation.
const OWN_DRAG = [
  '.swipeable-row',
  'input',
  'textarea',
  'select',
  '[contenteditable="true"]',
  '[role="dialog"]',
  '.adm-popup',
  '.adm-modal',
  '.adm-center-popup',
].join(',');

function scrollsSideways(el: Element | null): boolean {
  for (let node = el; node && node !== document.body; node = node.parentElement) {
    if (node.scrollWidth <= node.clientWidth) continue;
    const overflowX = getComputedStyle(node).overflowX;
    if (overflowX === 'auto' || overflowX === 'scroll') return true;
  }
  return false;
}

function ownsTheDrag(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  return target.closest(OWN_DRAG) !== null || scrollsSideways(target);
}

export function useSwipeBack() {
  const navigate = useNavigate();

  useEffect(() => {
    let startX = 0;
    let startY = 0;
    let startTime = 0;
    let tracking = false;

    function onTouchStart(e: TouchEvent) {
      const t = e.touches[0];
      if (e.touches.length === 1 && t.clientX <= EDGE_PX && !ownsTheDrag(e.target)) {
        startX = t.clientX;
        startY = t.clientY;
        startTime = Date.now();
        tracking = true;
      }
    }

    function onTouchEnd(e: TouchEvent) {
      if (!tracking) return;
      tracking = false;
      if (document.querySelector('[role="dialog"], .adm-popup')) return;
      const t = e.changedTouches[0];
      const dx = t.clientX - startX;
      const dy = t.clientY - startY;
      const dt = Date.now() - startTime;
      // Must be a horizontal right-swipe, not a vertical scroll.
      if (dx >= MIN_TRAVEL && Math.abs(dy) < 60 && Math.abs(dy) * 2 <= dx && dt <= MAX_DURATION) {
        // Back means an earlier page of this app. A screen opened straight from a link has none, and the page the
        // browser had before it may be another site: the feed is the place to go then.
        if (hasPreviousAppPage()) navigate(-1);
        else if (window.location.pathname !== '/') navigate('/', { replace: true });
      }
    }

    function onTouchMove(e: TouchEvent) {
      if (e.touches.length > 1) tracking = false;
    }

    function onTouchCancel() {
      tracking = false;
    }

    document.addEventListener('touchstart', onTouchStart, { passive: true });
    document.addEventListener('touchmove', onTouchMove, { passive: true });
    document.addEventListener('touchend', onTouchEnd, { passive: true });
    document.addEventListener('touchcancel', onTouchCancel, { passive: true });
    return () => {
      document.removeEventListener('touchstart', onTouchStart);
      document.removeEventListener('touchmove', onTouchMove);
      document.removeEventListener('touchend', onTouchEnd);
      document.removeEventListener('touchcancel', onTouchCancel);
    };
  }, [navigate]);
}

/**
 * Horizontal swipe-to-action for list rows.
 *
 * Tracks a single touch on the row, translates the inner content
 * horizontally, and exposes two callbacks:
 *   - onSwipeRight: triggered when the user swipes left→right
 *                   past THRESHOLD_PX (default "open / edit")
 *   - onSwipeLeft:  triggered when the user swipes right→left
 *                   past THRESHOLD_PX (default "delete")
 *
 * Visual behaviour:
 *   - While dragging, the row translates 1:1 with the finger
 *     (clamped between -MAX and +MAX).
 *   - Past the threshold, releasing fires the action — the consumer
 *     is responsible for snapping back / unmounting.
 *   - Below threshold, releasing springs the row back to rest.
 *
 * Why a hook instead of a library: we already own `useSwipeBack`
 * with the same touch-tracking shape. Keep dependencies minimal.
 */

import { useRef, useState, useCallback, type TouchEvent as ReactTouchEvent } from 'react';

// Travel thresholds tuned for ~412 CSS-px viewports on iOS Safari and
// Android Chrome — real-finger swipes rarely exceed 80 px before the
// user lifts, and a slow drag typically travels less than the user
// intended. 40 px is comfortable for one-handed use; anything
// shorter is interpreted as a tap.
const THRESHOLD_PX = 40;     // travel needed to commit an action
const MAX_OFFSET_PX = 84;    // hard cap so a long swipe doesn't yank the row off-screen
const COMMIT_VELOCITY = 0.3; // px/ms — fast flick also commits even if travel < threshold
const RUBBER_BAND = 0.45;    // resistance factor past MAX_OFFSET_PX

export type SwipeDirection = 'left' | 'right';

interface UseSwipeableRowOptions {
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
  /** Disable swiping while the row is in a non-interactive state. */
  disabled?: boolean;
}

export function useSwipeableRow({ onSwipeLeft, onSwipeRight, disabled }: UseSwipeableRowOptions) {
  const [offset, setOffset] = useState(0);
  // While dragging, suppress parent scroll handlers (PullToRefresh, etc.)
  const [dragging, setDragging] = useState(false);

  const startXRef = useRef(0);
  const startYRef = useRef(0);
  const startTimeRef = useRef(0);
  const lockedRef = useRef<SwipeDirection | null>(null);
  const offsetRef = useRef(0);

  // Keep ref in sync so the touchmove handler always sees the latest offset.
  offsetRef.current = offset;

  const onTouchStart = useCallback((e: ReactTouchEvent) => {
    if (disabled) return;
    const t = e.touches[0];
    startXRef.current = t.clientX;
    startYRef.current = t.clientY;
    startTimeRef.current = Date.now();
    lockedRef.current = null;
  }, [disabled]);

  const onTouchMove = useCallback((e: ReactTouchEvent) => {
    if (disabled) return;
    const t = e.touches[0];
    const dx = t.clientX - startXRef.current;
    const dy = t.clientY - startYRef.current;

    // Lock axis on the first significant move so vertical scroll
    // (within PullToRefresh) still works and a sloppy diagonal
    // swipe doesn't trigger both. The 4-px floor is small enough
    // that a slow, slightly-curved finger swipe still locks
    // horizontally — anything larger and we treat it as scroll.
    if (lockedRef.current === null) {
      if (Math.abs(dx) < 4 && Math.abs(dy) < 4) return;
      // Horizontal lock only if horizontal travel dominates.
      if (Math.abs(dx) > Math.abs(dy)) {
        lockedRef.current = dx > 0 ? 'right' : 'left';
        setDragging(true);
      } else {
        // Vertical — let the parent handle scroll and bail out.
        return;
      }
    }

    if (lockedRef.current === null) return;

    let next = dx;
    if (next > MAX_OFFSET_PX) {
      // Rubber-band beyond the cap so the row doesn't feel rigid.
      next = MAX_OFFSET_PX + (next - MAX_OFFSET_PX) * RUBBER_BAND;
    } else if (next < -MAX_OFFSET_PX) {
      next = -MAX_OFFSET_PX + (next + MAX_OFFSET_PX) * RUBBER_BAND;
    }
    setOffset(next);
  }, [disabled]);

  const onTouchEnd = useCallback(() => {
    if (disabled || !lockedRef.current) {
      setDragging(false);
      return;
    }
    const finalOffset = offsetRef.current;
    const elapsed = Math.max(1, Date.now() - startTimeRef.current);
    const velocity = Math.abs(finalOffset) / elapsed;
    const committed = Math.abs(finalOffset) >= THRESHOLD_PX || velocity >= COMMIT_VELOCITY;

    const direction = lockedRef.current;
    lockedRef.current = null;
    setDragging(false);

    if (committed) {
      // Animate to the edge so the user sees the action commit visually,
      // then fire the callback. Snap back happens implicitly when the
      // row is removed (delete) or when the next render lands.
      setOffset(direction === 'right' ? MAX_OFFSET_PX : -MAX_OFFSET_PX);
      if (direction === 'right') onSwipeRight?.();
      else onSwipeLeft?.();
    } else {
      // Spring back to rest.
      setOffset(0);
    }
  }, [disabled, onSwipeLeft, onSwipeRight]);

  const reset = useCallback(() => {
    setOffset(0);
    lockedRef.current = null;
    setDragging(false);
  }, []);

  return {
    offset,
    dragging,
    handlers: { onTouchStart, onTouchMove, onTouchEnd },
    reset,
  };
}

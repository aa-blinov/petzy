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
 *   - Past the threshold, releasing pins the row at the edge briefly
 *     (visual confirmation the swipe registered) then fires the action
 *     and springs back on its own — the consumer doesn't have to do
 *     anything to reset it, whether that action unmounts the row
 *     (delete-that-completes, navigate-to-edit) or just opens a
 *     confirmation dialog and leaves the row exactly where it was
 *     (delete-that-gets-cancelled — springing back regardless means
 *     there's no "stuck open" state to leave behind either way).
 *   - Below threshold, releasing springs the row back to rest.
 *
 * Input: Pointer Events, so mouse, touch and pen share one path.
 * This used to listen to touch events only, which meant the row could
 * not be swiped with a cursor at all.
 *
 * Rows open on tap as well (edit, or the file for a document); a swipe
 * swallows the click that follows it, so it never does both.
 *
 * Why a hook instead of a library: we already own `useSwipeBack`
 * with the same tracking shape. Keep dependencies minimal.
 */

import { useRef, useState, useCallback, useEffect, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent } from 'react';

// Travel thresholds tuned for ~412 CSS-px viewports on iOS Safari and
// Android Chrome — real-finger swipes rarely exceed 80 px before the
// user lifts, and a slow drag typically travels less than the user
// intended. 40 px is comfortable for one-handed use; anything
// shorter is interpreted as a tap.
const THRESHOLD_PX = 40;     // travel needed to commit an action
const MAX_OFFSET_PX = 84;    // hard cap so a long swipe doesn't yank the row off-screen
const COMMIT_VELOCITY = 0.3; // px/ms — fast flick also commits even if travel < threshold
const RUBBER_BAND = 0.45;    // resistance factor past MAX_OFFSET_PX
const SNAP_BACK_DELAY_MS = 220; // how long the row stays pinned at the edge before springing back

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
  // Whether THIS row actually received a pointerdown that's still live.
  // Without this, onPointerMove has no way to tell "the pointer is being
  // dragged" from "the mouse is merely hovering over me" — both fire the
  // same event. A hovered-but-never-pressed row has startXRef stuck at
  // its initial 0, so `dx = e.clientX - 0` was almost always > 4px,
  // making the row start "dragging" the instant a cursor passed over it.
  const isDownRef = useRef(false);
  // A horizontal drag ends in a click on the row like any press does;
  // rows now open on tap, so that click must not also fire.
  const draggedRef = useRef(false);
  const snapBackTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep ref in sync so the pointermove handler always sees the latest offset.
  useEffect(() => {
    offsetRef.current = offset;
  }, [offset]);

  useEffect(() => {
    return () => {
      if (snapBackTimeoutRef.current) clearTimeout(snapBackTimeoutRef.current);
    };
  }, []);

  const onPointerDown = useCallback((e: ReactPointerEvent) => {
    if (disabled) return;
    // Primary contact only: ignore right/middle clicks and extra fingers.
    if (!e.isPrimary || (e.pointerType === 'mouse' && e.button !== 0)) return;
    isDownRef.current = true;
    draggedRef.current = false;
    startXRef.current = e.clientX;
    startYRef.current = e.clientY;
    startTimeRef.current = Date.now();
    lockedRef.current = null;
  }, [disabled]);

  const onPointerMove = useCallback((e: ReactPointerEvent) => {
    if (disabled || !e.isPrimary || !isDownRef.current) return;
    const dx = e.clientX - startXRef.current;
    const dy = e.clientY - startYRef.current;

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
        draggedRef.current = true;
        setDragging(true);
        // Cancel the text selection a horizontal mouse drag would
        // otherwise start; touch is already handled by touch-action.
        e.preventDefault();
        // Capture only once this is confirmed to be a horizontal drag —
        // capturing unconditionally on pointerdown retargeted the
        // eventual click event to this element for every plain tap too,
        // so a row's own onClick (e.g. "tap to open") never fired.
        try {
          (e.currentTarget as Element).setPointerCapture(e.pointerId);
        } catch {
          /* capture unsupported or pointer already gone — tracking still works */
        }
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

  const onPointerUp = useCallback((e: ReactPointerEvent) => {
    isDownRef.current = false;
    try {
      (e.currentTarget as Element).releasePointerCapture(e.pointerId);
    } catch {
      /* capture was never taken */
    }
    if (disabled || !lockedRef.current) {
      setDragging(false);
      return;
    }
    const finalOffset = offsetRef.current;
    const elapsed = Math.max(1, Date.now() - startTimeRef.current);
    const velocity = Math.abs(finalOffset) / elapsed;
    const committed = Math.abs(finalOffset) >= THRESHOLD_PX || velocity >= COMMIT_VELOCITY;

    // Which side actually committed is decided by where the row rests at
    // release (finalOffset's sign) — not by `lockedRef`, which only ever
    // records which way the very first few pixels of the gesture went.
    // A drag that reverses mid-swipe (right, then back past center to
    // the left) used to still fire the right-side action because that
    // was the direction that happened to win the initial axis lock.
    const direction: SwipeDirection = finalOffset >= 0 ? 'right' : 'left';
    lockedRef.current = null;
    setDragging(false);

    if (committed) {
      // Pin to the edge so the user sees the swipe commit, then fire the
      // action and spring back on a timer regardless of what that action
      // does. Relying on the action itself to reset (e.g. only resetting
      // when the row unmounts) left the row visually stuck open whenever
      // it triggered a confirmation dialog that got cancelled instead of
      // removing the row.
      setOffset(direction === 'right' ? MAX_OFFSET_PX : -MAX_OFFSET_PX);
      if (snapBackTimeoutRef.current) clearTimeout(snapBackTimeoutRef.current);
      snapBackTimeoutRef.current = setTimeout(() => setOffset(0), SNAP_BACK_DELAY_MS);
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
    isDownRef.current = false;
    setDragging(false);
  }, []);

  return {
    offset,
    dragging,
    handlers: {
      onPointerDown,
      onPointerMove,
      onPointerUp,
      // A cancelled pointer (browser gesture, window blur) must not
      // leave the row stuck mid-swipe.
      onPointerCancel: onPointerUp,
      onClickCapture: (e: ReactMouseEvent) => {
        if (!draggedRef.current) return;
        draggedRef.current = false;
        e.stopPropagation();
        e.preventDefault();
      },
    },
    reset,
  };
}

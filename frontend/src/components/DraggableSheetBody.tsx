/**
 * Sheet contents that follow a downward drag and dismiss past a
 * threshold. Shared by every bottom sheet in the app (QuickAddSheet,
 * HistoryFilterSheet, ...) so the drag feel is identical everywhere.
 *
 * antd's own `closeOnSwipe` only reacts to @use-gesture's `swipe` flag,
 * which is velocity-gated: a quick flick closed the sheet, a deliberate
 * drag did not, and the sheet never followed the pointer to hint that
 * the gesture wasn't landing. With a cursor people drag slowly, so the
 * handle looked grabbable and did nothing at all.
 *
 * The offset lives on this wrapper rather than the popup body: antd
 * drives the body's transform with react-spring for the open/close
 * animation, and writing to the same property would fight it.
 *
 * `visible` resets the drag offset — but only when the sheet is
 * (re)opening, not when it closes. This used to be done by the parent
 * keying this component on `visible` itself, which remounted it (and
 * so snapped dragY back to 0) the instant a swipe-dismiss flipped
 * `visible` to false — i.e. at the exact moment antd's own closing
 * animation started. The content would jump back to rest and then
 * antd's slide-down would play on top of that, reading as the sheet
 * animating twice. Resetting only on the closed→open edge (below,
 * during render — React's sanctioned way to adjust state from a prop
 * change without an extra effect-triggered render) means a
 * swipe-dismiss keeps animating from wherever the finger left it.
 *
 * Content taller than the sheet's max height (HistoryFilterSheet, once
 * there are enough event types) scrolls inside antd's own `.adm-popup-
 * body` element (the caller opts in with `overflowY: 'auto'` on
 * `bodyStyle` — see HistoryFilterSheet). Dragging from inside that
 * scrolled content only dismisses the sheet once it's scrolled back to
 * the top and the finger keeps pulling down — same as a native bottom
 * sheet — so an ordinary scroll gesture doesn't fight the close
 * gesture, and a mid-scroll pull can't yank the sheet shut.
 */

import { useRef, useState, type ReactNode } from 'react';

/** Downward travel that commits the dismiss, in CSS px. */
const DISMISS_AFTER_PX = 90;

export function DraggableSheetBody({
  visible,
  onClose,
  children,
}: {
  visible: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  const [dragY, setDragY] = useState(0);
  // State, not a ref: the render below picks its transition from this,
  // and a ref read during render neither triggers an update nor is safe
  // under concurrent rendering.
  const [dragging, setDragging] = useState(false);
  const dragFrom = useRef<number | null>(null);
  // The scrollable ancestor for the drag in progress, if any — found by
  // walking up from wherever the pointer went down, since antd owns
  // that element and doesn't hand us a ref to it.
  const scrollElRef = useRef<HTMLElement | null>(null);

  const [wasVisible, setWasVisible] = useState(visible);
  if (visible !== wasVisible) {
    setWasVisible(visible);
    if (visible) setDragY(0);
  }

  const onPointerDown = (e: React.PointerEvent) => {
    if (!e.isPrimary || (e.pointerType === 'mouse' && e.button !== 0)) return;
    dragFrom.current = e.clientY;
    scrollElRef.current = (e.target as HTMLElement).closest('.adm-popup-body');
    setDragging(true);
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      /* capture unsupported — plain tracking still works */
    }
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (dragFrom.current === null) return;
    const delta = e.clientY - dragFrom.current;
    const atTop = (scrollElRef.current?.scrollTop ?? 0) <= 0;
    if (delta > 0 && atTop) {
      // Scrolled to the top (or never scrollable) and still pulling
      // down — drag the sheet closed instead of letting the content
      // rubber-band-scroll.
      e.preventDefault();
      setDragY(delta);
    } else {
      // Either scrolling normally, or pushed back up after a partial
      // dismiss drag — hand control back to the scrollview and
      // recalibrate so a later pull-at-top starts from 0, not from
      // wherever the finger happened to be when this branch began.
      if (dragY !== 0) setDragY(0);
      dragFrom.current = e.clientY;
    }
  };

  const onPointerUp = () => {
    if (dragFrom.current === null) return;
    const travelled = dragY;
    dragFrom.current = null;
    setDragging(false);
    if (travelled >= DISMISS_AFTER_PX) onClose();
    else setDragY(0);
  };

  return (
    <div
      style={{
        padding: 'var(--spacing-lg) var(--spacing-md) 0',
        transform: `translateY(${dragY}px)`,
        transition: dragging
          ? 'none'
          : `transform var(--motion-duration-base) var(--motion-ease-spring)`,
      }}
    >
      {/* Grab strip — the handle plus the space around it, so the target
          is a comfortable size rather than a 4 px bar. Always a drag
          surface regardless of scroll position, same as a native sheet's
          handle. */}
      <div
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        role="button"
        tabIndex={0}
        aria-label="Закрыть"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ' || e.key === 'Escape') {
            e.preventDefault();
            onClose();
          }
        }}
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: 28,
          marginBottom: 'var(--spacing-sm)',
          cursor: 'grab',
          touchAction: 'none',
        }}
      >
        <div
          style={{ width: 36, height: 4, borderRadius: 2, backgroundColor: 'var(--app-border-color)' }}
          aria-hidden
        />
      </div>

      {/* The content itself stays a normal in-flow block — antd's own
          .adm-popup-body is what actually scrolls (see the comment
          above) — this just also accepts the drag gesture so dismissing
          isn't limited to the thin handle strip above. */}
      <div
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        style={{ touchAction: 'pan-y' }}
      >
        {children}
      </div>
    </div>
  );
}

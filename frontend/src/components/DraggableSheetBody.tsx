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
 * This component — not antd's `.adm-popup-body` — owns the sheet's
 * visible card: background, rounded top corners, height bounds. It
 * used to be the other way round (the card look lived on `bodyStyle`,
 * this component was just a transparent, undecorated wrapper around
 * the handle + content), which meant dragging translated the handle
 * and content while the actual card background stayed put underneath
 * — the handle visibly pulled away from its own card instead of
 * carrying it along. antd's body is now just an invisible slot sized
 * to hold this card (for its own open/close slide animation); this
 * component is the one thing that moves as a single rigid block when
 * dragged, background included.
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
 * Content taller than the sheet's own max height (HistoryFilterSheet,
 * once there are enough event types) scrolls inside this component's
 * own content region instead of overflowing past the card's bounds.
 * Dragging from inside that scrolled content only dismisses the sheet
 * once it's scrolled back to the top and the finger keeps pulling
 * down — same as a native bottom sheet — so an ordinary scroll gesture
 * doesn't fight the close gesture, and a mid-scroll pull can't yank
 * the sheet shut.
 */

import { useRef, useState, type ReactNode } from 'react';

/** Downward travel that commits the dismiss, in CSS px. */
const DISMISS_AFTER_PX = 90;

export function DraggableSheetBody({
  visible,
  onClose,
  children,
  minHeight,
  maxHeight,
}: {
  visible: boolean;
  onClose: () => void;
  children: ReactNode;
  /** Floor for the card's height — content shorter than this still gets a full-size sheet. */
  minHeight?: string;
  /** Ceiling for the card's height — taller content scrolls inside instead of growing past it. */
  maxHeight?: string;
}) {
  const [dragY, setDragY] = useState(0);
  // State, not a ref: the render below picks its transition from this,
  // and a ref read during render neither triggers an update nor is safe
  // under concurrent rendering.
  const [dragging, setDragging] = useState(false);
  const dragFrom = useRef<number | null>(null);
  // The scrollable content region for the drag in progress, if any.
  const contentRef = useRef<HTMLDivElement>(null);

  const [wasVisible, setWasVisible] = useState(visible);
  if (visible !== wasVisible) {
    setWasVisible(visible);
    if (visible) setDragY(0);
  }

  const onPointerDown = (e: React.PointerEvent) => {
    if (!e.isPrimary || (e.pointerType === 'mouse' && e.button !== 0)) return;
    dragFrom.current = e.clientY;
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
    const atTop = (contentRef.current?.scrollTop ?? 0) <= 0;
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
        display: 'flex',
        flexDirection: 'column',
        minHeight,
        maxHeight,
        // The card itself — background and rounded top corners live
        // here so they travel with the drag instead of staying behind
        // as a static frame around moving content.
        backgroundColor: 'var(--app-card-background)',
        borderTopLeftRadius: 'var(--radius-xl)',
        borderTopRightRadius: 'var(--radius-xl)',
        // Clips scrolled content to the rounded corners instead of it
        // showing square behind them.
        overflow: 'hidden',
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
          flexShrink: 0,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: 28,
          marginTop: 'var(--spacing-sm)',
          cursor: 'grab',
          touchAction: 'none',
        }}
      >
        <div
          style={{ width: 36, height: 4, borderRadius: 2, backgroundColor: 'var(--app-border-color)' }}
          aria-hidden
        />
      </div>

      {/* Scrolls in place once content is taller than the card's own
          max height, instead of spilling past its rounded corners. */}
      <div
        ref={contentRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          // Stop an over-scroll at the top/bottom from chaining into
          // the page behind the sheet once this can't scroll further.
          overscrollBehavior: 'contain',
          touchAction: 'pan-y',
          padding: 'var(--spacing-md) var(--spacing-md) calc(var(--safe-area-bottom) + 24px)',
        }}
      >
        {children}
      </div>
    </div>
  );
}

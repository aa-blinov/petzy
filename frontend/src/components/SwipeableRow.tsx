import { type ReactNode } from 'react';
import { useSwipeableRow } from '../hooks/useSwipeableRow';
import { hapticFeedback } from '../utils/haptic';
import './SwipeableRow.css';

export interface SwipeAction {
  icon: ReactNode;
  label: string;
  /** CSS color expression for the action background. */
  color: string;
  onTrigger: () => void;
}

interface SwipeableRowProps {
  /** Action revealed when the row is swiped right (left→right finger motion). */
  leftAction?: SwipeAction;
  /** Action revealed when the row is swiped left (right→left finger motion). */
  rightAction?: SwipeAction;
  children: ReactNode;
  /** Disable swiping (e.g. while a delete dialog is open). */
  disabled?: boolean;
}

/**
 * Wraps a list row with horizontal swipe-to-action behaviour.
 *
 * - Swipe right (finger moves left→right): row translates right, reveals
 *   the `leftAction` (typically "open / edit"). Past threshold → fires.
 * - Swipe left  (finger moves right→left): row translates left, reveals
 *   the `rightAction` (typically "delete"). Past threshold → fires.
 *
 * The row content keeps its width and the action layers sit behind it
 * with `position: absolute` — the row translates on top of them.
 *
 * Uses the `useSwipeableRow` hook for touch tracking. CSS handles the
 * translation so it stays on the compositor (no re-renders per frame).
 */
export function SwipeableRow({ leftAction, rightAction, children, disabled }: SwipeableRowProps) {
  const handleLeft = () => {
    hapticFeedback('medium');
    rightAction?.onTrigger();
  };
  const handleRight = () => {
    hapticFeedback('light');
    leftAction?.onTrigger();
  };

  const { offset, dragging, handlers } = useSwipeableRow({
    onSwipeLeft: handleLeft,
    onSwipeRight: handleRight,
    disabled,
  });

  return (
    <div
      className={[
        'swipeable-row',
        dragging ? 'swipeable-row--dragging' : '',
        // Actions are only visible while the row is off its rest
        // position, so nothing underneath can peek out on a press.
        offset !== 0 ? 'swipeable-row--revealed' : '',
      ].filter(Boolean).join(' ')}
    >
      {/* Action layers — sit behind the row, fixed to the row's edges. */}
      {leftAction && (
        <div
          className="swipeable-row__action swipeable-row__action--left"
          style={{ backgroundColor: leftAction.color }}
          aria-hidden
        >
          <span className="swipeable-row__action-icon">{leftAction.icon}</span>
          <span className="swipeable-row__action-label">{leftAction.label}</span>
        </div>
      )}
      {rightAction && (
        <div
          className="swipeable-row__action swipeable-row__action--right"
          style={{ backgroundColor: rightAction.color }}
          aria-hidden
        >
          <span className="swipeable-row__action-icon">{rightAction.icon}</span>
          <span className="swipeable-row__action-label">{rightAction.label}</span>
        </div>
      )}

      {/* Foreground row — translates horizontally with the finger. */}
      <div
        className="swipeable-row__surface"
        style={{ transform: `translate3d(${offset}px, 0, 0)` }}
        {...handlers}
      >
        {children}
      </div>
    </div>
  );
}

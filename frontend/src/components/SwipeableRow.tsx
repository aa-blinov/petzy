import { useRef, type ReactNode } from 'react';
import { ActionSheet } from 'antd-mobile';
import { MoreOutline } from 'antd-mobile-icons';
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
  /** What the row is ("Рекс", "Прививка от бешенства"), so the actions
      button reads "Действия: Рекс" rather than a bare "Действия". */
  itemLabel?: string;
  /** The row's own tap action, when it has one (open a document), so
      the actions menu can offer it to people who can't tap the card. */
  openAction?: { label: string; onTrigger: () => void };
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
export function SwipeableRow({ leftAction, rightAction, children, disabled, itemLabel, openAction }: SwipeableRowProps) {
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const handleLeft = () => {
    hapticFeedback('medium');
    rightAction?.onTrigger();
  };
  const handleRight = () => {
    hapticFeedback('light');
    leftAction?.onTrigger();
  };

  // Swiping is the only way a touch user reaches edit/delete, and a
  // keyboard, switch or screen-reader user can't swipe at all. The same
  // actions sit behind a button that stays visually hidden until it
  // gets keyboard focus, and that screen readers always reach.
  const menuActions = [
    openAction && { key: 'open', text: openAction.label, onClick: openAction.onTrigger },
    leftAction && { key: 'left', text: leftAction.label, onClick: leftAction.onTrigger },
    rightAction && {
      key: 'right',
      text: rightAction.label,
      danger: rightAction.color === 'var(--app-danger-color)',
      onClick: rightAction.onTrigger,
    },
  ].filter((action): action is NonNullable<typeof action> => Boolean(action));

  const openMenu = () => {
    const sheetClass = `swipe-menu-${Date.now()}`;
    const handler = ActionSheet.show({
      popupClassName: sheetClass,
      actions: menuActions,
      cancelText: 'Отмена',
      closeOnAction: true,
      closeOnMaskClick: true,
      afterClose: () => {
        document.removeEventListener('keydown', onEscape);
        // Back where the user was, unless the action moved them on.
        if (menuButtonRef.current?.isConnected) menuButtonRef.current.focus();
      },
    });
    const onEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handler.close();
    };
    document.addEventListener('keydown', onEscape);
    // The sheet renders in a portal at the end of <body>, a few frames
    // after show(); once its first action exists, put focus there so the
    // keyboard user lands inside the sheet rather than behind its mask.
    let tries = 0;
    const focusFirstAction = () => {
      const first = document.querySelector<HTMLElement>(`.${sheetClass} .adm-action-sheet-button-item`);
      if (first) first.focus();
      else if (++tries < 30) requestAnimationFrame(focusFirstAction);
    };
    requestAnimationFrame(focusFirstAction);
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
        // Firefox ignores -webkit-user-drag (globals.css): without this a
        // swipe that starts on a photo drags the image, not the row.
        onDragStart={(e) => e.preventDefault()}
        {...handlers}
      >
        {children}
      </div>

      {/* After the row in DOM order: a screen reader reads the entry
          first, then offers its actions. */}
      {menuActions.length > 0 && (
        <button
          ref={menuButtonRef}
          type="button"
          className="swipeable-row__menu"
          aria-label={itemLabel ? `Действия: ${itemLabel}` : 'Действия'}
          aria-haspopup="dialog"
          disabled={disabled}
          onClick={openMenu}
        >
          <MoreOutline aria-hidden />
        </button>
      )}
    </div>
  );
}

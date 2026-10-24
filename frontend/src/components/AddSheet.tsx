import { createElement, type ReactNode } from 'react';
import { Popup } from 'antd-mobile';
import type { LucideIcon } from 'lucide-react';

import { pastelColorMap } from '../utils/constants';
import { hapticFeedback } from '../utils/haptic';
import { DraggableSheetBody } from './DraggableSheetBody';
import './AddSheet.css';

/** The one name of every sheet that asks what to add. */
export const ADD_SHEET_TITLE = 'Что добавить?';

/**
 * The sheet under every «+»: the feed's, the medical card's blocks and the Documents list. One look (the feed's coloured tiles),
 * one title. What it holds is the screen's own: tiles (`AddTiles`, `AddTile`), quiet copper lines (`AddLink`), a sub-title.
 */
export function AddSheet({
  visible,
  onClose,
  title = ADD_SHEET_TITLE,
  maxHeight = '75vh',
  children,
}: {
  visible: boolean;
  onClose: () => void;
  title?: string;
  maxHeight?: string;
  children: ReactNode;
}) {
  return (
    <Popup visible={visible} onMaskClick={onClose} position="bottom" closeOnSwipe bodyStyle={{ background: 'transparent' }}>
      <DraggableSheetBody visible={visible} onClose={onClose} maxHeight={maxHeight} label={title}>
        <h2 className="addsheet__title">{title}</h2>
        {children}
      </DraggableSheetBody>
    </Popup>
  );
}

/** A grid of tiles: two columns, one for a single long choice (`single`) and on a narrow phone. */
export function AddTiles({ single = false, children }: { single?: boolean; children: ReactNode }) {
  return <div className={`addsheet__grid${single ? ' addsheet__grid--single' : ''}`}>{children}</div>;
}

/** One choice: a pastel tile with an icon and a name, `badge` the small mark under the name («Свой»). */
export function AddTile({
  label,
  icon,
  color = 'blue',
  badge,
  onClick,
}: {
  label: string;
  icon?: LucideIcon;
  color?: string;
  badge?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="addsheet__tile tap-feedback"
      style={{ background: pastelColorMap[color] ?? 'var(--tile-blue)' }}
      onClick={() => {
        hapticFeedback('light');
        onClick();
      }}
    >
      {icon && (
        <span className="addsheet__icon" aria-hidden>
          {createElement(icon, { size: 20, strokeWidth: 2 })}
        </span>
      )}
      <span className="addsheet__text">
        <span className="addsheet__label">{label}</span>
        {/* Outside the clamp: a long name must not push the mark that says the type is the person's own out of sight. */}
        {badge && <span className="addsheet__badge">{badge}</span>}
      </span>
    </button>
  );
}

/** A quiet copper line under the tiles: another way on, not another choice of the same kind. */
export function AddLink({ onClick, expanded, children }: { onClick: () => void; expanded?: boolean; children: ReactNode }) {
  return (
    <button type="button" className="addsheet__link tap-feedback" aria-expanded={expanded} onClick={onClick}>
      {children}
    </button>
  );
}

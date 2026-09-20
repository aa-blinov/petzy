/**
 * Bottom sheet listing all record types in a 2-column grid.
 *
 * Replaces the older ActionSheet (vertical list of titles) with a
 * grid of icon-tiles so the user can see all options at a glance and
 * tap the one they want in a single gesture.
 *
 * Uses antd-mobile `Popup` rather than `ActionSheet` — ActionSheet
 * ignores children and only renders the `actions` array, so any custom
 * body content has to live inside a Popup.
 */

import { Popup, Grid } from 'antd-mobile';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { tilesConfig } from '../utils/tilesConfig';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { usePet } from '../hooks/usePet';
import { hapticFeedback } from '../utils/haptic';
import { pastelColorMap, typeIconMap } from '../utils/constants';


interface QuickAddSheetProps {
  visible: boolean;
  onClose: () => void;
}


/** Downward travel that commits the dismiss, in CSS px. */
const DISMISS_AFTER_PX = 90;

export function QuickAddSheet({ visible, onClose }: QuickAddSheetProps) {
  // Drag-to-dismiss.
  //
  // antd's own `closeOnSwipe` only reacts to @use-gesture's `swipe`
  // flag, which is velocity-gated — a quick flick closes the sheet, a
  // deliberate drag does not. With a cursor people drag slowly, so the
  // handle looked grabbable and did nothing, and the sheet never
  // followed the pointer to hint that the gesture wasn't landing.
  //
  // The offset is applied to an inner wrapper rather than the popup
  // body: antd drives the body's transform with react-spring for the
  // open/close animation, and writing to the same property would fight
  // it — the mistake that once pinned popups in place.
  const [dragY, setDragY] = useState(0);
  const dragFrom = useRef<number | null>(null);

  // Reopening must not inherit the offset the last drag left behind.
  useEffect(() => {
    if (visible) setDragY(0);
  }, [visible]);

  const onPointerDown = (e: React.PointerEvent) => {
    if (!e.isPrimary || (e.pointerType === 'mouse' && e.button !== 0)) return;
    dragFrom.current = e.clientY;
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      /* capture unsupported — plain tracking still works */
    }
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (dragFrom.current === null) return;
    // Downward only: dragging up shouldn't lift the sheet off its edge.
    setDragY(Math.max(0, e.clientY - dragFrom.current));
  };

  const onPointerUp = () => {
    if (dragFrom.current === null) return;
    const travelled = dragY;
    dragFrom.current = null;
    if (travelled >= DISMISS_AFTER_PX) onClose();
    else setDragY(0);
  };

  const navigate = useNavigate();
  const { selectedPetId } = usePet();
  const { tilesSettings } = usePetTilesSettings(selectedPetId);

  const tiles = tilesConfig
    .filter(t => t.isTile !== false && tilesSettings.visible[t.id] !== false)
    .sort((a, b) => {
      const ai = tilesSettings.order.indexOf(a.id);
      const bi = tilesSettings.order.indexOf(b.id);
      return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    });

  return (
    <Popup
      visible={visible}
      onMaskClick={onClose}
      position="bottom"
      closeOnSwipe
      bodyStyle={{
        borderTopLeftRadius: 'var(--radius-xl)',
        borderTopRightRadius: 'var(--radius-xl)',
        backgroundColor: 'var(--app-card-background)',
        minHeight: '60vh',
        paddingBottom: 'calc(var(--safe-area-bottom) + 24px)',
      }}
    >
      <div
        style={{
          padding: 'var(--spacing-lg) var(--spacing-md) 0',
          transform: `translateY(${dragY}px)`,
          transition: dragFrom.current === null
            ? `transform var(--motion-duration-base) var(--motion-ease-spring)`
            : 'none',
        }}
      >
        {/* Grab strip — the handle plus the padding around it, so the
            target is a comfortable size rather than a 4 px bar. */}
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
            style={{
              width: 36,
              height: 4,
              borderRadius: 2,
              backgroundColor: 'var(--app-border-color)',
            }}
            aria-hidden
          />
        </div>

        {/* Title */}
        <h3
          className="section-header"
          style={{
            marginBottom: 'var(--spacing-lg)',
            paddingLeft: 4,
            fontSize: '1.125rem',
          }}
        >
          Что записать?
        </h3>

        <Grid columns={2} gap={12}>
          {tiles.map(tile => {
            const bg = pastelColorMap[tile.color] ?? 'var(--tile-blue)';
            const Icon = typeIconMap[tile.id];
            return (
              <Grid.Item key={tile.id}>
                <button
                  type="button"
                  onClick={() => {
                    hapticFeedback('light');
                    onClose();
                    navigate(`/form/${tile.id}`);
                  }}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    gap: '8px',
                    padding: '14px',
                    height: '100px',
                    width: '100%',
                    background: bg,
                    border: 'none',
                    borderRadius: '14px',
                    color: 'var(--app-text-on-tile)',
                    textAlign: 'left',
                    cursor: 'pointer',
                    boxShadow: 'var(--app-shadow-light)',
                  }}
                >
                  {Icon && (
                    <Icon
                      size={24}
                      strokeWidth={2}
                      style={{ display: 'block', color: 'var(--app-text-on-tile)' }}
                    />
                  )}
                  <span
                    style={{
                      fontSize: '14px',
                      fontWeight: 600,
                      lineHeight: 1.25,
                      letterSpacing: '-0.01em',
                    }}
                  >
                    {tile.title}
                  </span>
                </button>
              </Grid.Item>
            );
          })}
        </Grid>
      </div>
    </Popup>
  );
}

/**
 * Bottom sheet for picking the History screen's type filter.
 *
 * Replaces the old horizontally-scrolling chip rail: with more than a
 * handful of event types the rail needed a swipe just to see what was
 * even available, and nothing on screen hinted that it scrolled. This
 * mirrors QuickAddSheet's grid-of-tiles look (same component people
 * already know from the dashboard's "+" button) instead of introducing
 * a third pattern, but adds a checkmark on the active tile since a
 * filter — unlike "what do you want to add" — has a current selection
 * to show.
 */

import { Popup, Grid } from 'antd-mobile';
import { Check } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { pastelColorMap } from '../utils/constants';
import { hapticFeedback } from '../utils/haptic';
import { DraggableSheetBody } from './DraggableSheetBody';

export interface HistoryFilterOption {
  id: string;
  label: string;
  color: string;
  Icon: LucideIcon | null;
}

interface HistoryFilterSheetProps {
  visible: boolean;
  onClose: () => void;
  options: HistoryFilterOption[];
  activeId: string;
  onSelect: (id: string) => void;
}

export function HistoryFilterSheet({ visible, onClose, options, activeId, onSelect }: HistoryFilterSheetProps) {
  return (
    <Popup
      visible={visible}
      onMaskClick={onClose}
      position="bottom"
      closeOnSwipe
      // The visible card (background, radius, height) lives on
      // DraggableSheetBody now, so the whole card moves as one rigid
      // block while dragging — this slot just needs to be invisible.
      bodyStyle={{ background: 'transparent' }}
    >
      <DraggableSheetBody visible={visible} onClose={onClose} maxHeight="75vh">
        <h3
          className="section-header"
          style={{
            marginBottom: 'var(--spacing-lg)',
            paddingLeft: 4,
            fontSize: '1.125rem',
          }}
        >
          Показать записи
        </h3>

        <Grid columns={2} gap={10}>
          {options.map(option => {
            const active = option.id === activeId;
            const bg = pastelColorMap[option.color] ?? 'var(--tile-blue)';
            const Icon = option.Icon;
            return (
              <Grid.Item key={option.id}>
                <button
                  type="button"
                  onClick={() => {
                    hapticFeedback('light');
                    onSelect(option.id);
                    onClose();
                  }}
                  aria-pressed={active}
                  style={{
                    position: 'relative',
                    display: 'flex',
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '12px',
                    height: '56px',
                    width: '100%',
                    background: bg,
                    border: active ? '2px solid var(--app-text-on-tile)' : '2px solid transparent',
                    // Concentric with the sheet's own 24px corner, 12px
                    // (--spacing-md) in from it: 24 − 12 = 12.
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--app-text-on-tile)',
                    textAlign: 'left',
                    cursor: 'pointer',
                    boxShadow: 'var(--app-shadow-light)',
                  }}
                >
                  {Icon && (
                    <Icon
                      size={20}
                      strokeWidth={2}
                      style={{ display: 'block', flexShrink: 0, color: 'var(--app-text-on-tile)' }}
                    />
                  )}
                  <span
                    style={{
                      flex: 1,
                      minWidth: 0,
                      fontSize: '13px',
                      fontWeight: 600,
                      lineHeight: 1.25,
                      letterSpacing: '-0.01em',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {option.label}
                  </span>
                  {active && (
                    <div
                      aria-hidden
                      style={{
                        flexShrink: 0,
                        width: 18,
                        height: 18,
                        borderRadius: '50%',
                        background: 'var(--app-text-on-tile)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Check size={12} strokeWidth={3} style={{ color: bg }} />
                    </div>
                  )}
                </button>
              </Grid.Item>
            );
          })}
        </Grid>
      </DraggableSheetBody>
    </Popup>
  );
}

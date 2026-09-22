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
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

import { buildTiles } from '../utils/tilesConfig';
import { buildEventDisplayConfigs } from '../utils/eventDisplay';
import { useEventTypes } from '../hooks/useEventTypes';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { usePet } from '../hooks/usePet';
import { hapticFeedback } from '../utils/haptic';
import { pastelColorMap } from '../utils/constants';
import { DraggableSheetBody } from './DraggableSheetBody';


interface QuickAddSheetProps {
  visible: boolean;
  onClose: () => void;
}

export function QuickAddSheet({ visible, onClose }: QuickAddSheetProps) {
  const navigate = useNavigate();
  const { selectedPetId } = usePet();
  const { tilesSettings } = usePetTilesSettings(selectedPetId);
  const { eventTypes } = useEventTypes();
  const displayConfigs = useMemo(() => buildEventDisplayConfigs(eventTypes), [eventTypes]);

  const tiles = buildTiles(eventTypes)
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
      bodyStyle={{ background: 'transparent' }}
    >
      <DraggableSheetBody visible={visible} onClose={onClose} minHeight="60vh">

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
            const Icon = displayConfigs[tile.id]?.icon;
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
      </DraggableSheetBody>
    </Popup>
  );
}

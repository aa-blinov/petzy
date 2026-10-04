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

import { buildTiles, byTileOrder, isTileShown } from '../utils/tilesConfig';
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
  const { selectedPetId, getSelectedPet } = usePet();
  const { tilesSettings } = usePetTilesSettings(selectedPetId);
  const { eventTypes } = useEventTypes();
  const displayConfigs = useMemo(() => buildEventDisplayConfigs(eventTypes), [eventTypes]);

  const tiles = byTileOrder(
    buildTiles(eventTypes).filter((t) => t.isTile !== false && isTileShown(tilesSettings, t.id)),
    tilesSettings,
  );

  return (
    <Popup
      visible={visible}
      onMaskClick={onClose}
      position="bottom"
      closeOnSwipe
      bodyStyle={{ background: 'transparent' }}
    >
      {/* Sized to its tiles; many event types scroll inside, same cap as
          HistoryFilterSheet. */}
      <DraggableSheetBody visible={visible} onClose={onClose} maxHeight="75vh" label="Что записать?">

        {/* Title */}
        <h2
          className="section-header"
          style={{
            marginBottom: 'var(--spacing-lg)',
            paddingLeft: 4,
            fontSize: '1.125rem',
          }}
        >
          Что записать?
        </h2>

        {tiles.length === 0 && (
          // Every tile is hidden in the settings: said, with the way back, not an empty sheet.
          <div style={{ padding: 'var(--spacing-md) 4px var(--spacing-lg)', color: 'var(--app-text-secondary)' }}>
            <p style={{ margin: '0 0 var(--spacing-md)' }}>В окне «+» ничего нет: добавьте события питомца</p>
            <button
              type="button"
              className="touch-target"
              style={{ border: 'none', background: 'none', padding: 0, font: 'inherit', fontWeight: 600, color: 'var(--app-accent-deep)', cursor: 'pointer' }}
              onClick={() => {
                onClose();
                navigate('/pet-events');
              }}
            >
              Добавить события
            </button>
          </div>
        )}

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
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: 'var(--spacing-md)',
                    padding: '12px',
                    height: '56px',
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
                      size={20}
                      strokeWidth={2}
                      style={{ display: 'block', flexShrink: 0, color: 'var(--app-text-on-tile)' }}
                    />
                  )}
                  <span
                    style={{
                      fontSize: '13px',
                      fontWeight: 600,
                      lineHeight: 1.25,
                      letterSpacing: '-0.01em',
                      overflow: 'hidden',
                      // Two lines before a cut: «Приступ астмы» on a narrow phone is not «Приступ аст…».
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflowWrap: 'anywhere',
                      minWidth: 0,
                      textAlign: 'left',
                    }}
                  >
                    {tile.title}
                  </span>
                </button>
              </Grid.Item>
            );
          })}
        </Grid>

        {/* A new pet starts with a few events; the rest of the catalogue is one tap from here, for whoever may change them. */}
        {tiles.length > 0 && getSelectedPet?.current_user_is_owner !== false && (
          <button
            type="button"
            className="tap-feedback"
            onClick={() => {
              onClose();
              navigate('/pet-events');
            }}
            style={{ width: '100%', minHeight: 'var(--touch-min)', marginTop: 'var(--spacing-md)', background: 'none', border: 'none', font: 'inherit', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-accent-deep)', cursor: 'pointer' }}
          >
            Другие события
          </button>
        )}
      </DraggableSheetBody>
    </Popup>
  );
}

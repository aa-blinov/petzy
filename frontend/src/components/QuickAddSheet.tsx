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
import { useMemo, useState } from 'react';
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
  // The types this pet does not show as tiles: a one-off record of one of them is logged from here, without adding the type to
  // the pet first.
  const others = buildTiles(eventTypes).filter((t) => t.isTile !== false && !isTileShown(tilesSettings, t.id));
  const [othersOpen, setOthersOpen] = useState(false);
  const isOwner = getSelectedPet?.current_user_is_owner !== false;
  // The list of the others closes with the sheet: the next opening starts with the pet's own tiles.
  const close = () => {
    setOthersOpen(false);
    onClose();
  };

  const renderTiles = (list: typeof tiles) => (
        <Grid columns={2} gap={12}>
          {list.map(tile => {
            const bg = pastelColorMap[tile.color] ?? 'var(--tile-blue)';
            const Icon = displayConfigs[tile.id]?.icon;
            return (
              <Grid.Item key={tile.id}>
                <button
                  type="button"
                  onClick={() => {
                    hapticFeedback('light');
                    close();
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
                  <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0, textAlign: 'left' }}>
                    <span
                      style={{
                        fontSize: 'var(--text-sm)',
                        fontWeight: 500,
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
                    {/* Outside the clamp: a long name must not push the mark that says the type is the person's own out of sight. */}
                    {tile.custom && (
                      <span style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 400, opacity: 0.75, marginTop: 2 }}>Свой</span>
                    )}
                  </span>
                </button>
              </Grid.Item>
            );
          })}
        </Grid>
  );

  return (
    <Popup
      visible={visible}
      onMaskClick={close}
      position="bottom"
      closeOnSwipe
      bodyStyle={{ background: 'transparent' }}
    >
      {/* Sized to its tiles; many event types scroll inside, same cap as
          HistoryFilterSheet. */}
      <DraggableSheetBody visible={visible} onClose={close} maxHeight="75vh" label="Что записать?">

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
              style={{ border: 'none', background: 'none', padding: 0, font: 'inherit', fontWeight: 500, color: 'var(--app-accent-deep)', cursor: 'pointer' }}
              onClick={() => {
                close();
                navigate('/pet-events');
              }}
            >
              Добавить события
            </button>
          </div>
        )}

        {renderTiles(tiles)}

        {/* A new pet starts with a few events; the rest of the catalogue is here, one tap from a record, for whoever may log. */}
        {tiles.length > 0 && others.length > 0 && !othersOpen && (
          <button
            type="button"
            className="tap-feedback"
            aria-expanded={false}
            onClick={() => setOthersOpen(true)}
            style={{ width: '100%', minHeight: 'var(--touch-min)', marginTop: 'var(--spacing-md)', background: 'none', border: 'none', font: 'inherit', fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--app-accent-deep)', cursor: 'pointer' }}
          >
            Другие события
          </button>
        )}
        {(othersOpen || (tiles.length === 0 && others.length > 0)) && (
          <>
            <h3 className="section-header" style={{ margin: 'var(--spacing-lg) 0 var(--spacing-sm)', paddingLeft: 4, fontSize: 'var(--text-md)' }}>
              Другие события
            </h3>
            {renderTiles(others)}
          </>
        )}
        {/* Which events stay in this window is the owner's to change. */}
        {tiles.length > 0 && isOwner && (
          <button
            type="button"
            className="tap-feedback"
            onClick={() => {
              close();
              navigate('/pet-events');
            }}
            style={{ width: '100%', minHeight: 'var(--touch-min)', marginTop: 'var(--spacing-md)', background: 'none', border: 'none', font: 'inherit', fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--app-accent-deep)', cursor: 'pointer' }}
          >
            Настроить события питомца
          </button>
        )}
      </DraggableSheetBody>
    </Popup>
  );
}

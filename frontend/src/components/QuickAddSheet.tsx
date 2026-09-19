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
import { useNavigate } from 'react-router-dom';

import { tilesConfig } from '../utils/tilesConfig';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { usePet } from '../hooks/usePet';
import { hapticFeedback } from '../utils/haptic';
import { pastelColorMap } from '../utils/constants';


interface QuickAddSheetProps {
  visible: boolean;
  onClose: () => void;
}


export function QuickAddSheet({ visible, onClose }: QuickAddSheetProps) {
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
      bodyStyle={{
        borderTopLeftRadius: 'var(--radius-xl)',
        borderTopRightRadius: 'var(--radius-xl)',
        backgroundColor: 'var(--app-card-background)',
        minHeight: '60vh',
        paddingBottom: 'calc(var(--safe-area-bottom) + 24px)',
      }}
    >
      <div style={{ padding: 'var(--spacing-lg) var(--spacing-md) 0' }}>
        {/* Drag handle */}
        <div
          style={{
            width: 36,
            height: 4,
            borderRadius: 2,
            backgroundColor: 'var(--app-border-color)',
            margin: '0 auto var(--spacing-md)',
          }}
          aria-hidden
        />

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
                    height: '92px',
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
                  <span style={{ fontSize: '15px', fontWeight: 700, lineHeight: 1.2 }}>
                    {tile.title}
                  </span>
                  <span style={{ fontSize: '12px', opacity: 0.7, lineHeight: 1.2 }}>
                    {tile.subtitle}
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

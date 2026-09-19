/**
 * Bottom sheet listing all record types in a 2-column grid.
 *
 * Replaces the older ActionSheet (vertical list of titles) with a
 * grid of icon-tiles so the user can see all options at a glance and
 * tap the one they want in a single gesture.
 */

import { ActionSheet, Grid } from 'antd-mobile';
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
    <ActionSheet
      visible={visible}
      onClose={onClose}
      closeOnAction
      title="Что записать?"
      styles={{
        body: { minHeight: "60vh" },
      }}
    >
      <div style={{ padding: "0 var(--spacing-md) var(--spacing-lg)" }}>
        <Grid
          columns={2}
          gap={12}
          data={tiles.map(tile => ({
            key: tile.id,
            title: tile.title,
            subtitle: tile.subtitle,
            bg: pastelColorMap[tile.color] ?? 'var(--tile-blue)',
            tile,
          }))}
          renderItem={item => (
            <button
              key={item.key}
              type="button"
              onClick={() => {
                hapticFeedback("light");
                onClose();
                navigate(`/form/${item.tile.id}`);
              }}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                justifyContent: "space-between",
                gap: "8px",
                padding: "14px",
                height: "92px",
                background: item.bg,
                border: "none",
                borderRadius: "12px",
                color: "var(--app-text-on-tile)",
                textAlign: "left",
                cursor: "pointer",
              }}
            >
              <span style={{ fontSize: "15px", fontWeight: 700, lineHeight: 1.2 }}>
                {item.title}
              </span>
              <span style={{ fontSize: "12px", opacity: 0.7, lineHeight: 1.2 }}>
                {item.subtitle}
              </span>
            </button>
          )}
        />
      </div>
    </ActionSheet>
  );
}
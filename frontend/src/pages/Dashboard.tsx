import { useNavigate } from 'react-router-dom';
import { Card } from 'antd-mobile';
import { tilesConfig } from '../utils/tilesConfig';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { usePet } from '../hooks/usePet';


// Пастельные цвета для кнопок
const pastelColorMap: Record<string, string> = {
  brown: 'var(--tile-brown)',
  orange: 'var(--tile-orange)',
  red: 'var(--tile-red)',
  green: 'var(--tile-green)',
  purple: 'var(--tile-purple)',
  teal: 'var(--tile-teal)',
  cyan: 'var(--tile-cyan)',
  yellow: 'var(--tile-yellow)',
  blue: 'var(--tile-blue)',
  pink: 'var(--tile-pink)',
};

export function Dashboard() {
  const navigate = useNavigate();
  const { selectedPetId } = usePet();
  const { tilesSettings } = usePetTilesSettings(selectedPetId);

  // Filter and sort tiles based on settings
  const visibleTiles = tilesConfig
    .filter(tile => {
      // Hard filter: some items are not meant to be tiles (e.g. medications live separately)
      if (tile.isTile === false) return false;
      return tilesSettings.visible[tile.id] !== false;
    })
    .sort((a, b) => {
      const aIndex = tilesSettings.order.indexOf(a.id);
      const bIndex = tilesSettings.order.indexOf(b.id);
      return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
    });

  const handleTileClick = (tile: typeof tilesConfig[0]) => {
    if (tile.screen.includes('-form')) {
      const formType = tile.id;
      navigate(`/form/${formType}`);
    }
  };

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div
          className="safe-area-padding"
          style={{
            marginBottom: 'var(--spacing-lg)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            minHeight: '40px',
          }}
        >
          <h2 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Дневник</h2>
        </div>

        <div
          className="safe-area-padding"
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--spacing-md)'
          }}
        >
          {visibleTiles.map(tile => {
            const backgroundColor = pastelColorMap[tile.color] || 'var(--tile-blue)';
            return (
              <Card
                key={tile.id}
                style={{
                  backgroundColor: backgroundColor,
                  cursor: 'pointer',
                  WebkitTapHighlightColor: 'transparent',
                  borderRadius: 'var(--radius-md)',
                  border: 'none',
                  boxShadow: 'var(--app-shadow)',
                }}
                onClick={() => handleTileClick(tile)}
              >
                <div style={{ padding: 'var(--spacing-lg)' }}>
                  <h3 style={{ margin: `0 0 var(--spacing-sm) 0`, fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--app-text-on-tile)' }}>
                    {tile.title}
                  </h3>
                  <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
                    {tile.subtitle}
                  </p>
                </div>
              </Card>
            );
          })}
        </div>


      </div>
    </div>
  );
}


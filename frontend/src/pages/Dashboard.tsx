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
    <div style={{
      minHeight: '100vh',
      paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
      paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
      backgroundColor: 'var(--app-page-background)',
      color: 'var(--app-text-color)'
    }}>
      <div style={{
        maxWidth: '800px',
        margin: '0 auto'
      }}>
        <div style={{
          marginBottom: '16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          minHeight: '40px',
          paddingLeft: 'max(16px, env(safe-area-inset-left))',
          paddingRight: 'max(16px, env(safe-area-inset-right))'
        }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: '24px', fontWeight: 600, margin: 0 }}>Дневник</h2>
        </div>

        <div style={{
          paddingLeft: 'max(16px, env(safe-area-inset-left))',
          paddingRight: 'max(16px, env(safe-area-inset-right))',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}>
          {visibleTiles.map(tile => {
            const backgroundColor = pastelColorMap[tile.color] || 'var(--tile-blue)';
            return (
              <Card
                key={tile.id}
                style={{
                  backgroundColor: backgroundColor,
                  cursor: 'pointer',
                  WebkitTapHighlightColor: 'transparent',
                  borderRadius: '12px',
                  border: 'none',
                  boxShadow: 'var(--app-shadow)',
                }}
                onClick={() => handleTileClick(tile)}
              >
                <div style={{ padding: '16px' }}>
                  <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: 600, color: 'var(--app-text-on-tile)' }}>
                    {tile.title}
                  </h3>
                  <p style={{ margin: 0, fontSize: '14px', color: 'var(--app-text-secondary)' }}>
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


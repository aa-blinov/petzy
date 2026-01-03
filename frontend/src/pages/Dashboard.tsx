import { useNavigate } from 'react-router-dom';
import { Card } from 'antd-mobile';
import { tilesConfig } from '../utils/tilesConfig';
import { useTilesSettings } from '../hooks/useTilesSettings';

// Пастельные цвета для кнопок
const pastelColorMap: Record<string, string> = {
  brown: '#E8D5C4',    // Пастельный коричневый
  orange: '#FFE5B4',   // Пастельный оранжевый
  red: '#FFD1CC',      // Пастельный красный
  green: '#D4F4DD',    // Пастельный зеленый
  purple: '#E8D5F2',   // Пастельный фиолетовый
  teal: '#D4F4F1',     // Пастельный бирюзовый
  cyan: '#D4F0FF',     // Пастельный голубой
  yellow: '#FFF9D4',   // Пастельный желтый
  blue: '#D4E8FF',     // Пастельный синий
  pink: '#FFE5EB',     // Пастельный розовый
};

export function Dashboard() {
  const navigate = useNavigate();
  const { tilesSettings } = useTilesSettings();

  // Filter and sort tiles based on settings
  const visibleTiles = tilesConfig
    .filter(tile => {
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
          paddingLeft: 'max(16px, env(safe-area-inset-left))', 
          paddingRight: 'max(16px, env(safe-area-inset-right))' 
        }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: '24px', fontWeight: 600, margin: 0 }}>Дашборд</h2>
        </div>
        <div style={{ 
          paddingLeft: 'max(16px, env(safe-area-inset-left))',
          paddingRight: 'max(16px, env(safe-area-inset-right))',
          display: 'flex', 
          flexDirection: 'column', 
          gap: '12px'
        }}>
          {visibleTiles.map(tile => {
          const backgroundColor = pastelColorMap[tile.color] || '#D4E8FF';
          return (
            <Card
              key={tile.id}
              style={{
                backgroundColor: backgroundColor,
                cursor: 'pointer',
                WebkitTapHighlightColor: 'transparent',
                borderRadius: '12px',
                border: 'none',
                boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
              }}
              onClick={() => handleTileClick(tile)}
            >
              <div style={{ padding: '16px' }}>
                <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: 600, color: '#000000' }}>
                  {tile.title}
                </h3>
                <p style={{ margin: 0, fontSize: '14px', color: '#666666' }}>
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


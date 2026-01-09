import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Tabs, Button } from 'antd-mobile';
import { usePet } from '../hooks/usePet';
import { historyConfig } from '../utils/historyConfig';
import { HistoryTab } from '../components/HistoryTab';
import { HistoryChart } from '../components/HistoryChart';
import { ExportModal } from '../components/ExportModal';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { tilesConfig } from '../utils/tilesConfig';

// Пастельные цвета для вкладок (соответствуют дневнику)
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

export function History() {
  const { selectedPetId } = usePet();
  const { tilesSettings } = usePetTilesSettings(selectedPetId);
  const [searchParams, setSearchParams] = useSearchParams();

  // Получаем вкладки, отсортированные и отфильтрованные так же, как в дневнике
  const tabs = useMemo(() => {
    return tilesConfig
      .filter(tile => tilesSettings.visible[tile.id] !== false)
      .sort((a, b) => {
        const aIndex = tilesSettings.order.indexOf(a.id);
        const bIndex = tilesSettings.order.indexOf(b.id);
        return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
      })
      .map(tile => ({
        key: tile.id,
        title: historyConfig[tile.id as keyof typeof historyConfig]?.displayName || tile.title,
        color: tile.color,
      }));
  }, [tilesSettings]);

  // Получаем активную вкладку из URL параметра или используем первую по умолчанию
  const getActiveTabFromUrl = (): string => {
    const tabFromUrl = searchParams.get('tab');
    if (tabFromUrl && tabFromUrl in historyConfig) {
      return tabFromUrl;
    }
    return tabs[0]?.key || 'feeding';
  };

  const [activeTab, setActiveTab] = useState<string>(getActiveTabFromUrl);
  const [exportVisible, setExportVisible] = useState(false);
  const [viewMode, setViewMode] = useState<'list' | 'chart'>('list');

  // Синхронизируем активную вкладку с URL при изменении параметра
  useEffect(() => {
    const tabFromUrl = searchParams.get('tab');
    if (tabFromUrl && tabFromUrl in historyConfig && tabFromUrl !== activeTab) {
      setActiveTab(tabFromUrl);
    } else if (!tabFromUrl && tabs.length > 0 && activeTab !== tabs[0].key) {
      setSearchParams({ tab: activeTab });
    }
  }, [searchParams, activeTab, setSearchParams, tabs]);

  // Обновляем URL при изменении вкладки
  const handleTabChange = (key: string) => {
    setActiveTab(key);
    setSearchParams({ tab: key });
  };

  if (!selectedPetId) {
    return (
      <div style={{ minHeight: '100vh', padding: '16px' }}>
        <p>Выберите животное в меню навигации для просмотра истории</p>
      </div>
    );
  }

  return (
    <div style={{
      minHeight: '100vh',
      paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
      paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
      backgroundColor: 'var(--app-page-background)',
      color: 'var(--app-text-color)'
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{
          marginBottom: '16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          minHeight: '40px',
          paddingLeft: 'max(16px, env(safe-area-inset-left))',
          paddingRight: 'max(16px, env(safe-area-inset-right))'
        }}>
          <h2 style={{ fontSize: '24px', margin: 0, fontWeight: 600, color: 'var(--app-text-color)' }}>История записей</h2>
          <Button
            size="small"
            fill="outline"
            onClick={() => setExportVisible(true)}
            style={{ borderColor: 'var(--adm-color-border)' }}
          >
            Экспорт
          </Button>
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={handleTabChange}
          style={{
            marginBottom: '16px',
            '--active-line-color': pastelColorMap[tabs.find(t => t.key === activeTab)?.color || 'blue'] || '#D4E8FF',
            '--active-title-color': 'var(--app-text-color)',
            '--title-font-size': '16px',
            '--content-padding': '0',
          } as React.CSSProperties}
        >
          {tabs.map(tab => (
            <Tabs.Tab
              key={tab.key}
              title={tab.title}
            />
          ))}
        </Tabs>

        {/* View mode toggle */}
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          marginBottom: '16px',
          padding: '0 16px'
        }}>
          <div style={{
            display: 'flex',
            backgroundColor: 'var(--app-card-background)',
            padding: '4px',
            borderRadius: '8px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
          }}>
            <Button
              size="mini"
              fill={viewMode === 'list' ? 'solid' : 'none'}
              color={viewMode === 'list' ? 'primary' : 'default'}
              onClick={() => setViewMode('list')}
              style={{ borderRadius: '6px', padding: '4px 12px' }}
            >
              Список
            </Button>
            <Button
              size="mini"
              fill={viewMode === 'chart' ? 'solid' : 'none'}
              color={viewMode === 'chart' ? 'primary' : 'default'}
              onClick={() => setViewMode('chart')}
              style={{ borderRadius: '6px', padding: '4px 12px' }}
            >
              График
            </Button>
          </div>
        </div>

        <div style={{ minHeight: '400px' }}>
          {viewMode === 'list' ? (
            <HistoryTab type={activeTab} petId={selectedPetId} activeTab={activeTab} />
          ) : (
            <div style={{ paddingLeft: 'max(16px, env(safe-area-inset-left))', paddingRight: 'max(16px, env(safe-area-inset-right))' }}>
              <HistoryChart type={activeTab} petId={selectedPetId} />
            </div>
          )}
        </div>
      </div>

      <ExportModal
        visible={exportVisible}
        onClose={() => setExportVisible(false)}
        petId={selectedPetId}
        defaultType={activeTab}
      />
    </div>
  );
}

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
      <div style={{ minHeight: '100vh', padding: 'var(--spacing-lg)' }}>
        <p>Выберите животное в меню навигации для просмотра истории</p>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{
          marginBottom: 'var(--spacing-lg)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          minHeight: '40px',
        }}>
          <h2 style={{ fontSize: 'var(--text-xxl)', margin: 0, fontWeight: 600, color: 'var(--app-text-color)' }}>История записей</h2>
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
            marginBottom: 'var(--spacing-lg)',
            '--active-line-color': pastelColorMap[tabs.find(t => t.key === activeTab)?.color || 'blue'] || 'var(--tile-blue)',
            '--active-title-color': 'var(--app-text-color)',
            '--title-font-size': 'var(--text-md)',
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
          marginBottom: 'var(--spacing-lg)',
          padding: `0 var(--spacing-lg)`
        }}>
          <div style={{
            display: 'flex',
            backgroundColor: 'var(--app-card-background)',
            padding: 'var(--spacing-xs)',
            borderRadius: 'var(--radius-sm)',
            boxShadow: 'var(--app-shadow-light)'
          }}>
            <Button
              size="mini"
              fill={viewMode === 'list' ? 'solid' : 'none'}
              color={viewMode === 'list' ? 'primary' : 'default'}
              onClick={() => setViewMode('list')}
              style={{ borderRadius: '6px', padding: `var(--spacing-xs) var(--spacing-md)` }}
            >
              Список
            </Button>
            <Button
              size="mini"
              fill={viewMode === 'chart' ? 'solid' : 'none'}
              color={viewMode === 'chart' ? 'primary' : 'default'}
              onClick={() => setViewMode('chart')}
              style={{ borderRadius: '6px', padding: `var(--spacing-xs) var(--spacing-md)` }}
            >
              График
            </Button>
          </div>
        </div>

        <div style={{ minHeight: '400px' }}>
          {viewMode === 'list' ? (
            <HistoryTab type={activeTab} petId={selectedPetId} activeTab={activeTab} />
          ) : (
            <div className="safe-area-padding">
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

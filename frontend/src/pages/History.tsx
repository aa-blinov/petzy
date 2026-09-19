import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Tabs, Button } from 'antd-mobile';
import { Download } from 'lucide-react';
import { usePet } from '../hooks/usePet';
import { historyConfig } from '../utils/historyConfig';
import { HistoryTab } from '../components/HistoryTab';
import { HistoryChart } from '../components/HistoryChart';
import { ExportModal } from '../components/ExportModal';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { tilesConfig } from '../utils/tilesConfig';
import { pastelColorMap } from '../utils/constants';
import { hapticFeedback } from '../utils/haptic';

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
    hapticFeedback('light');
    setActiveTab(key);
    setSearchParams({ tab: key });
  };

  const handleViewModeChange = (mode: 'list' | 'chart') => {
    hapticFeedback('light');
    setViewMode(mode);
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
          marginBottom: 'var(--spacing-sm)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          minHeight: '40px',
        }}>
          <h1
            className="display-headline"
            style={{ fontSize: '24px', margin: 0 }}
          >
            История записей
          </h1>
          <button
            type="button"
            onClick={() => setExportVisible(true)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--app-accent-deep)',
              fontWeight: 500,
              fontSize: 'var(--text-sm)',
              cursor: 'pointer',
              padding: '8px 4px',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <Download size={16} strokeWidth={2} style={{ display: 'block' }} />
            Экспорт
          </button>
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={handleTabChange}
          style={{
            marginBottom: 'var(--spacing-md)',
            '--active-line-color': pastelColorMap[tabs.find(t => t.key === activeTab)?.color || 'blue'] || 'var(--tile-blue)',
            '--active-title-color': 'var(--app-text-color)',
            '--title-font-size': 'var(--text-sm)',
            '--content-padding': '0',
          } as React.CSSProperties}
          className="history-tabs-scrollable"
        >
          {tabs.map(tab => (
            <Tabs.Tab
              key={tab.key}
              title={tab.title}
            />
          ))}
        </Tabs>

        {/* View mode toggle — compact pill, sits flush right */}
        <div style={{
          display: 'flex',
          justifyContent: 'flex-end',
          marginBottom: 'var(--spacing-md)',
          padding: `0 var(--spacing-lg)`,
        }}>
          <div style={{
            display: 'flex',
            backgroundColor: 'var(--app-card-background)',
            padding: 3,
            borderRadius: '999px',
            boxShadow: 'var(--app-shadow-light)',
            border: '1px solid var(--app-border-color)',
          }}>
            <button
              type="button"
              onClick={() => handleViewModeChange('list')}
              style={{
                background: viewMode === 'list' ? 'var(--app-primary-color)' : 'transparent',
                color: viewMode === 'list' ? '#FFFFFF' : 'var(--app-text-secondary)',
                border: 'none',
                borderRadius: '999px',
                padding: '4px 14px',
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 180ms ease',
              }}
            >
              Список
            </button>
            <button
              type="button"
              onClick={() => handleViewModeChange('chart')}
              style={{
                background: viewMode === 'chart' ? 'var(--app-primary-color)' : 'transparent',
                color: viewMode === 'chart' ? '#FFFFFF' : 'var(--app-text-secondary)',
                border: 'none',
                borderRadius: '999px',
                padding: '4px 14px',
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 180ms ease',
              }}
            >
              График
            </button>
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

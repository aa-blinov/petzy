import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Tabs, Button } from 'antd-mobile';
import { usePet } from '../hooks/usePet';
import { historyConfig } from '../utils/historyConfig';
import { HistoryTab } from '../components/HistoryTab';
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

  // Синхронизируем активную вкладку с URL при изменении параметра
  useEffect(() => {
    const tabFromUrl = searchParams.get('tab');
    if (tabFromUrl && tabFromUrl in historyConfig && tabFromUrl !== activeTab) {
      setActiveTab(tabFromUrl);
    } else if (!tabFromUrl && activeTab !== Object.keys(historyConfig)[0]) {
      // Если параметра нет, но активная вкладка не первая, обновляем URL
      setSearchParams({ tab: activeTab });
    }
  }, [searchParams, activeTab, setSearchParams]);

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
            marginBottom: '24px',
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
            >
              <HistoryTab type={tab.key} petId={selectedPetId} activeTab={activeTab} />
            </Tabs.Tab>
          ))}
        </Tabs>
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


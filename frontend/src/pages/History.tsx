import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Tabs, Button } from 'antd-mobile';
import { usePet } from '../hooks/usePet';
import { historyConfig } from '../utils/historyConfig';
import { HistoryTab } from '../components/HistoryTab';
import { ExportModal } from '../components/ExportModal';

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
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Получаем активную вкладку из URL параметра или используем первую по умолчанию
  const getActiveTabFromUrl = (): string => {
    const tabFromUrl = searchParams.get('tab');
    if (tabFromUrl && tabFromUrl in historyConfig) {
      return tabFromUrl;
    }
    return Object.keys(historyConfig)[0] || 'feeding';
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

  const tabs = Object.entries(historyConfig).map(([key, config]) => ({
    key,
    title: config.displayName,
    color: config.color,
  }));

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


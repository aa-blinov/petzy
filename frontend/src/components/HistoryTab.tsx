import { useInfiniteQuery } from '@tanstack/react-query';
import { Button } from 'antd-mobile';
import { healthRecordsService } from '../services/healthRecords.service';
import { historyConfig } from '../utils/historyConfig';
import { HistoryItem } from './HistoryItem';
import type { HealthRecordType } from '../utils/constants';
import { LoadingSpinner } from './LoadingSpinner';

interface HistoryTabProps {
  type: string;
  petId: string;
  activeTab: string;
}

export function HistoryTab({ type, petId, activeTab }: HistoryTabProps) {
  const config = historyConfig[type as keyof typeof historyConfig];
  const pageSize = 100;

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    error
  } = useInfiniteQuery({
    queryKey: ['history', type, petId],
    queryFn: async ({ pageParam = 1 }) => {
      const response = await healthRecordsService.getList(type as HealthRecordType, petId, pageParam as number, pageSize) as any;
      const dataKey = config.dataKey;
      const items = Array.isArray(response[dataKey]) ? response[dataKey] : [];
      return {
        items,
        page: response.page,
        total: response.total,
        hasMore: response.page * pageSize < response.total
      };
    },
    getNextPageParam: (lastPage) => {
      return lastPage.hasMore ? lastPage.page + 1 : undefined;
    },
    initialPageParam: 1
  });

  if (isLoading) {
    return <LoadingSpinner fullscreen={false} />;
  }

  if (error) {
    return (
      <p style={{ color: '#FF453A', textAlign: 'center', padding: '32px 0' }}>
        Ошибка загрузки данных
      </p>
    );
  }

  const allItems = data?.pages.flatMap(page => page.items) || [];

  if (allItems.length === 0) {
    return (
      <p style={{ color: 'var(--app-text-secondary)', textAlign: 'center', padding: '32px 0' }}>
        Нет записей
      </p>
    );
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
      paddingLeft: 'max(16px, env(safe-area-inset-left))',
      paddingRight: 'max(16px, env(safe-area-inset-right))',
      paddingTop: '16px'
    }}>
      {allItems.map(item => (
        <HistoryItem
          key={item._id}
          item={item}
          config={config}
          type={type}
          activeTab={activeTab}
        />
      ))}

      {hasNextPage && (
        <div style={{
          marginTop: '24px',
          paddingTop: '24px',
          borderTop: '1px solid var(--app-border-color)',
          display: 'flex',
          justifyContent: 'center'
        }}>
          <Button
            fill="outline"
            onClick={() => {
              fetchNextPage();
            }}
            disabled={isFetchingNextPage}
            loading={isFetchingNextPage}
          >
            {isFetchingNextPage ? 'Загрузка...' : 'Загрузить еще'}
          </Button>
        </div>
      )}
    </div>
  );
}


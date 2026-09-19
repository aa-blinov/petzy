import { useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { Button, PullToRefresh } from 'antd-mobile';
import { healthRecordsService } from '../services/healthRecords.service';
import { historyConfig } from '../utils/historyConfig';
import { HistoryItem } from './HistoryItem';
import type { HealthRecordType } from '../utils/constants';
import { HistoryItemSkeleton } from './Skeletons';
import { hapticFeedback } from '../utils/haptic';

interface HistoryTabProps {
  type: string;
  petId: string;
  activeTab: string;
}

/** Format a YYYY-MM-DD dateStr as a friendly Russian relative or absolute label. */
function formatDateHeader(dateStr: string): string {
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;

  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  const pad = (n: number) => n.toString().padStart(2, '0');
  const todayStr = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
  const yesterdayStr = `${yesterday.getFullYear()}-${pad(yesterday.getMonth() + 1)}-${pad(yesterday.getDate())}`;

  if (dateStr === todayStr) return 'Сегодня';
  if (dateStr === yesterdayStr) return 'Вчера';
  return `${parts[2]}.${parts[1]}.${parts[0]}`;
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
    error,
    refetch,
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

  // Group items by date — gives the list the same structural
  // readability as the dashboard timeline.
  const groupedItems = useMemo(() => {
    const allItems = data?.pages.flatMap(page => page.items) || [];
    const groups: Record<string, any[]> = {};
    for (const item of allItems) {
      const dateStr = String(item.date_time ?? '').split(' ')[0];
      if (!groups[dateStr]) groups[dateStr] = [];
      groups[dateStr].push(item);
    }
    // Sort date keys desc so most-recent day shows first.
    return Object.entries(groups).sort(([a], [b]) => b.localeCompare(a));
  }, [data]);

  const content = (() => {
    if (isLoading) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <HistoryItemSkeleton />
          <HistoryItemSkeleton />
          <HistoryItemSkeleton />
        </div>
      );
    }

    if (error) {
      return (
        <p style={{ color: 'var(--app-danger-color)', textAlign: 'center', padding: '32px 0' }}>
          Ошибка загрузки данных
        </p>
      );
    }

    if (groupedItems.length === 0) {
      return (
        <p style={{ color: 'var(--app-text-secondary)', textAlign: 'center', padding: '32px 0' }}>
          Нет записей
        </p>
      );
    }

    return (
      <>
        {groupedItems.map(([dateStr, itemsForDate]) => (
          <div key={dateStr} style={{ marginBottom: 'var(--spacing-lg)' }}>
            <h3
              className="section-header"
              style={{
                marginBottom: '10px',
                paddingLeft: 4,
              }}
            >
              {formatDateHeader(dateStr)}
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {itemsForDate.map((item: any, index: number) => (
                <div
                  key={item._id}
                  className={`animate-slide-up animate-stagger-${Math.min(index + 1, 6)}`}
                >
                  <HistoryItem
                    item={item}
                    config={config}
                    type={type}
                    activeTab={activeTab}
                  />
                </div>
              ))}
            </div>
          </div>
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
                hapticFeedback('light');
                fetchNextPage();
              }}
              disabled={isFetchingNextPage}
              loading={isFetchingNextPage}
            >
              {isFetchingNextPage ? 'Загрузка...' : 'Загрузить ещё'}
            </Button>
          </div>
        )}
      </>
    );
  })();

  return (
    <PullToRefresh
      onRefresh={async () => {
        hapticFeedback('medium');
        await refetch();
      }}
      headHeight={48}
    >
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        paddingLeft: 'max(16px, env(safe-area-inset-left))',
        paddingRight: 'max(16px, env(safe-area-inset-right))',
        paddingTop: '8px'
      }}>
        {content}
      </div>
    </PullToRefresh>
  );
}

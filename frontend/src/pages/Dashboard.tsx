import { useEffect, useRef, useState, useMemo, type ReactNode } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useInfiniteQuery } from '@tanstack/react-query';
import { Button, PullToRefresh } from 'antd-mobile';
import { PawPrint, Notebook } from 'lucide-react';

import { buildEventDisplayConfigs } from '../utils/eventDisplay';
import { useEventTypes } from '../hooks/useEventTypes';
import { usePet } from '../hooks/usePet';
import { useSession } from '../hooks/useSession';
import { hadPets, isOnboardingDismissed, rememberHavingPets } from '../utils/onboarding';
import { hapticFeedback } from '../utils/haptic';
import { healthRecordsService, type HealthRecord } from '../services/healthRecords.service';
import { HistoryItem, SwipeHint } from '../components/HistoryItem';
import { useHiddenRecords } from '../utils/deferredDelete';
import { uniqueById } from '../utils/uniqueById';
import { Fab } from '../components/Fab';
import { DashboardSkeleton } from '../components/Skeletons';
import { NextDoseWidget } from '../components/NextDoseWidget';
import { PendingIntakesNotice } from '../components/PendingIntakesNotice';
import { PetSummaryCard } from '../components/PetSummaryCard';
import { QuickAddSheet } from '../components/QuickAddSheet';
import { EmptyState } from '../components/EmptyState';
import { LoadError } from '../components/LoadError';
import { PendingInvites } from '../components/PendingInvites';
import { usePetInvites } from '../hooks/usePetInvites';

/** The next page comes when the end of the list comes near (the button stays, for whoever uses it). */
function AutoLoadMore({ onVisible, disabled, children }: { onVisible: () => void; disabled: boolean; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const latest = useRef(onVisible);
  useEffect(() => {
    latest.current = onVisible;
  });
  useEffect(() => {
    const el = ref.current;
    if (!el || disabled || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) latest.current();
    }, { rootMargin: '300px' });
    observer.observe(el);
    return () => observer.disconnect();
  }, [disabled]);
  return <div ref={ref}>{children}</div>;
}

export function Dashboard() {
  const navigate = useNavigate();
  const { selectedPetId, getSelectedPet, pets, isFetched: petsFetched, isError: petsFailed, refetchPets } = usePet();
  const { username } = useSession();
  const { eventTypes } = useEventTypes();
  const historyConfig = useMemo(() => buildEventDisplayConfigs(eventTypes), [eventTypes]);

  const [actionSheetVisible, setActionSheetVisible] = useState(false);
  const invites = usePetInvites();
  useEffect(() => {
    if (pets.length > 0) rememberHavingPets(username);
  }, [pets.length, username]);


  const pageSize = 20;

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    error,
    refetch,
  } = useInfiniteQuery({
    queryKey: ['timeline', selectedPetId],
    queryFn: async ({ pageParam = 1 }) => {
      if (!selectedPetId) return { items: [], page: 1, total: 0, hasMore: false };
      const response = await healthRecordsService.getTimeline(
        selectedPetId,
        pageParam as number,
        pageSize,
        // No filtering — the timeline shows every event in chronological order.
        'all'
      );
      return {
        items: response.items || [],
        page: response.page,
        total: response.total,
        hasMore: response.page * pageSize < response.total
      };
    },
    getNextPageParam: (lastPage) => (lastPage.hasMore ? lastPage.page + 1 : undefined),
    initialPageParam: 1,
    enabled: !!selectedPetId,
    // What another person wrote while the app was in the background is there when it comes back to the front.
    refetchOnWindowFocus: true,
  });

  // Records deleted a moment ago, «Отменить» still on offer, are left out.
  const hiddenRecords = useHiddenRecords();
  // Only what can be drawn: a record of a kind the app no longer knows would otherwise leave its day with a header and no card.
  const allItems = useMemo(
    () =>
      uniqueById(data?.pages.flatMap(page => page.items) ?? []).filter(
        item => !hiddenRecords.has(item._id) && !!item.record_type && !!historyConfig[item.record_type],
      ),
    [data, hiddenRecords, historyConfig],
  );

  const groupedItems = useMemo(() => {
    return allItems.reduce<Record<string, HealthRecord[]>>((acc, item) => {
      const dateStr = String(item.date_time ?? '').split(' ')[0];
      if (!acc[dateStr]) acc[dateStr] = [];
      acc[dateStr].push(item);
      return acc;
    }, {});
  }, [allItems]);

  const formatDateHeader = (dateStr: string) => {
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
  };

  // A brand-new account lands here with nothing to show: send it through
  // onboarding (which ends by adding the first pet). Someone who opted to
  // wait for a shared pet instead gets a plain explanation, not a feed
  // that offers to log events for a pet that doesn't exist.
  // The roster didn't load: that says nothing about whether there are
  // pets, so no onboarding and no «Питомцев пока нет».
  if (petsFailed) {
    return (
      <div className="page-container">
        <div className="max-width-container">
          <h1 className="sr-only">Лента</h1>
          <LoadError what="питомцев" onRetry={refetchPets} />
        </div>
      </div>
    );
  }

  if (petsFetched && pets.length === 0) {
    // Someone invited to a family's pet answers that first, instead of
    // being walked through adding a pet of their own.
    if (!invites.isFetched) return <DashboardSkeleton />;
    if ((invites.data?.length ?? 0) > 0) {
      return (
        <div className="page-container">
          <div className="max-width-container safe-area-padding">
            <h1 className="sr-only">Лента</h1>
            <PendingInvites />
            <Button block fill="none" onClick={() => navigate('/welcome')}>
              Добавить своего питомца
            </Button>
          </div>
        </div>
      );
    }
    const lostAccess = hadPets(username);
    if (!isOnboardingDismissed(username) && !lostAccess) return <Navigate to="/welcome" replace />;
    return (
      <div className="page-container">
        <div className="max-width-container">
          <h1 className="sr-only">Лента</h1>
          <EmptyState
            icon={PawPrint}
            title={lostAccess ? 'Доступ к питомцу закрыт' : 'Питомцев пока нет'}
            description={
              lostAccess
                ? `Владелец закрыл вам доступ или удалил питомца. Если с вами поделятся снова, он появится здесь. Ваш логин: ${username ?? ''}`
                : `Когда с вами поделятся питомцем, он появится здесь. Ваш логин: ${username ?? ''}`
            }
            actionLabel="Добавить своего"
            onAction={() => navigate('/welcome')}
          />
        </div>
      </div>
    );
  }

  return (
    <>
      {/* ─── Main scrollable content ─── */}
      <div className="page-container" style={{ paddingBottom: '80px' }}>
        <div className="max-width-container">
          {/* The feed has no visible title (the tab says where you are),
              but a screen reader still needs the page's h1. */}
          <h1 className="sr-only">Лента</h1>
          <PullToRefresh
            onRefresh={async () => {
              hapticFeedback('medium');
              await refetch();
            }}
            headHeight={48}
          >

          {/* Timeline Content */}
          <div className="safe-area-padding" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <PendingInvites />
            {/* Pet at-a-glance summary */}
            {getSelectedPet && (
              <PetSummaryCard pet={getSelectedPet} />
            )}

            {/* Widget for upcoming medication block */}
            <div className="feed-widgets">
              <PendingIntakesNotice />
              <NextDoseWidget />
            </div>

            {/* The feed's request waits for a chosen pet, so it is not loading while the list of pets is still
                arriving and there is nothing chosen yet. That is not an empty feed, and «лента пока пуста»
                said so to people whose pet was a second away. */}
            {isLoading || !petsFetched ? (
              <DashboardSkeleton />
            ) : error ? (
              <LoadError what="ленту" onRetry={refetch} />
            ) : allItems.length === 0 ? (
              <EmptyState
                icon={Notebook}
                title="Лента пока пуста"
                description="Кормления, вес, лекарства и прививки появятся здесь, как только вы их добавите"
                // The round «+» is right there and does the same thing. The button is here anyway:
                // an empty state that only says what to do elsewhere leaves someone who does not
                // see the corner (or cannot press it) with nothing to press.
                actionLabel="Записать событие"
                onAction={() => setActionSheetVisible(true)}
              />
            ) : (
              <>
                <SwipeHint />
                {Object.entries(groupedItems).map(([dateStr, itemsForDate]) => (
                  <div key={dateStr} style={{ marginBottom: '16px' }}>
                    {/* Date separator */}
                    <h2
                      className="section-header"
                      style={{
                        marginBottom: 'var(--spacing-sm)',
                        marginTop: '4px',
                        paddingLeft: '4px',
                      }}
                    >
                      {formatDateHeader(dateStr)}
                    </h2>

                    {/* Cards for the day */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {itemsForDate.map((item: HealthRecord) => {
                        const type = item.record_type;
                        const config = type ? historyConfig[type] : undefined;
                        if (!type || !config) return null; // not reached: the list was filtered to what can be drawn
                        return (
                          <HistoryItem
                            key={item._id}
                            item={item}
                            config={config}
                            type={type}
                          />
                        );
                      })}
                    </div>
                  </div>
                ))}

                {hasNextPage && (
                  <AutoLoadMore onVisible={() => { void fetchNextPage(); }} disabled={isFetchingNextPage}>
                    <div style={{ display: 'flex', justifyContent: 'center', paddingBottom: 'var(--spacing-xl)' }}>
                      <Button
                        fill="outline"
                        color="primary"
                        onClick={() => { fetchNextPage(); }}
                        disabled={isFetchingNextPage}
                        loading={isFetchingNextPage}
                      >
                        {isFetchingNextPage ? 'Загрузка...' : 'Загрузить ещё'}
                      </Button>
                    </div>
                  </AutoLoadMore>
                )}

                {/* One way out of the feed to everything it does not show: the feed is today and what is next,
                    the History screen is everything and the charts. Settings had a row to it, so the only way
                    there from the feed was a detour through Settings. */}
                <div style={{ display: 'flex', justifyContent: 'center', paddingBottom: 'var(--spacing-xl)' }}>
                  <Button fill="outline" color="primary" onClick={() => navigate('/history')}>
                    Вся история
                  </Button>
                </div>
              </>
            )}
          </div>
          </PullToRefresh>

        </div>
      </div>

      {/* The round «+» is the one every list has (components/Fab): in a portal, and stepping aside on a scroll down, so that it
          does not stand over the time and the arrow of the cards it passes. A real button: a keyboard or a screen reader adds a
          record with it too. */}
      <Fab label="Добавить запись" onClick={() => setActionSheetVisible(true)} popup />

      {/* Add Record — quick-add grid */}
      <QuickAddSheet
        visible={actionSheetVisible}
        onClose={() => setActionSheetVisible(false)}
      />
    </>
  );
}

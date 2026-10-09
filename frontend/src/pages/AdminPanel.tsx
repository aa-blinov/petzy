import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Dialog, PullToRefresh, SearchBar, Button } from 'antd-mobile';
import { Pencil, ShieldAlert, UserX, UserCheck, Users } from 'lucide-react';
import { useAdmin } from '../hooks/useAdmin';
import { usersService, type User } from '../services/users.service';
import { adminService, ADMIN_USERS_PER_PAGE } from '../services/admin.service';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SkeletonList } from '../components/Skeletons';
import { hapticFeedback } from '../utils/haptic';
import { useAuth } from '../hooks/useAuth';
import { CardChevron } from '../components/CardChevron';
import { SwipeableRow } from '../components/SwipeableRow';
import { EmptyState } from '../components/EmptyState';
import { LoadError } from '../components/LoadError';
import { Fab } from '../components/Fab';
import { formatRelativeDate } from '../utils/relativeTime';
import { getApiErrorMessage } from '../utils/apiError';

/** The admin list carries the whole user document, so whether the email was confirmed is on it. */
type AdminUser = User & { email_verified?: boolean };

export function AdminPanel() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isAdmin, isLoading: isAdminLoading } = useAdmin();
  const { username: currentUsername } = useAuth();
  // State for alert messages
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // A failed request is not an empty list: «Пользователей пока нет» after a failed fetch told the owner
  // that everyone had been deleted, and offered to add them again. Loading, error and empty are three states.
  // One page at a time, newest first: the list used to arrive whole, which grows with every account.
  const [search, setSearch] = useState('');
  // What the list is fetched by: typing should not fire a request per letter.
  const [appliedSearch, setAppliedSearch] = useState('');
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => {
      setAppliedSearch(search.trim());
      // A new question starts again from the first page: the answer to the old one may sit elsewhere.
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const {
    data: usersPage,
    isLoading: usersLoading,
    isError: usersFailed,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['users', appliedSearch, page],
    queryFn: () => adminService.getUsers({ page, query: appliedSearch }),
    enabled: isAdmin,
  });

  const users = usersPage?.users ?? [];
  const total = usersPage?.total ?? 0;
  const lastPage = Math.max(1, Math.ceil(total / ADMIN_USERS_PER_PAGE));


  // The endpoint only ever deactivates (soft delete — `is_active: false`),
  // never removes the row. Labelling this "Удалить" everywhere used to
  // promise something that didn't happen, and there was no way back: once
  // deactivated, a user stayed that way forever with no UI path to
  // reactivate them. Now both directions are real actions with honest names.
  const deactivateMutation = useMutation({
    mutationFn: (username: string) => usersService.deleteUser(username),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setSuccess(data.message);
      setTimeout(() => setSuccess(null), 3000);
    },
    onError: (err: unknown) => {
      setError(getApiErrorMessage(err, 'Не удалось деактивировать пользователя'));
    },
  });

  const activateMutation = useMutation({
    mutationFn: (username: string) => usersService.updateUser(username, { is_active: true }),
    // Both directions say what the server said: deactivation used to show the server's «Пользователь деактивирован»
    // while activation showed a word typed on this screen, so two rows about one thing spoke differently.
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setSuccess(data.message);
      setTimeout(() => setSuccess(null), 3000);
    },
    onError: (err: unknown) => {
      setError(getApiErrorMessage(err, 'Не удалось активировать пользователя'));
    },
  });

  const [deleteDialog, setDeleteDialog] = useState<{ visible: boolean; username: string | null }>({
    visible: false,
    username: null
  });

  const handleDelete = (username: string) => {
    hapticFeedback('medium');
    setDeleteDialog({ visible: true, username });
  };

  const handleActivate = (username: string) => {
    hapticFeedback('light');
    activateMutation.mutate(username);
  };

  const handleEdit = (user: User) => {
    hapticFeedback('light');
    navigate(`/admin/users/${user.username}/edit`);
  };

  const handleNewUser = () => {
    hapticFeedback('light');
    navigate('/admin/users/new');
  };

  if (isAdminLoading) {
    return <LoadingSpinner />;
  }

  // Not an admin: the same thing every other screen says when there is nothing to do here, with the way back
  // into the settings this screen was opened from. A red bar at the top of an empty page left the person
  // guessing where to go.
  if (!isAdmin) {
    return (
      <div className="page-container">
        <div className="max-width-container">
          <EmptyState
            icon={ShieldAlert}
            heading="h1"
            title="Здесь нужны права администратора"
            description="Учётными записями управляет администратор. Ваши питомцы, записи и настройки остаются на своих экранах"
            actionLabel="Назад в настройки"
            onAction={() => navigate('/settings')}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="page-container fab-page">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{
          marginBottom: 'var(--spacing-lg)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          minHeight: '40px',
        }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 500, margin: 0 }}>Админ-панель</h1>
        </div>

        {error && (
          <div className="safe-area-padding" style={{ paddingBottom: 'var(--spacing-lg)' }}>
            <Alert type="error" message={error} onClose={() => setError(null)} />
          </div>
        )}
        {success && (
          <div className="safe-area-padding" style={{ paddingBottom: 'var(--spacing-lg)' }}>
            <Alert type="success" message={success} onClose={() => setSuccess(null)} />
          </div>
        )}

        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          {/* Same .section-header as Settings, so the admin screen reads
              as part of the app rather than a bare CRUD table. */}
          <h2 className="section-header" style={{ fontSize: 'var(--text-lg)' }}>Пользователи</h2>
        </div>

        {/* The search is admin-only by nature: it runs over every account in the app,
            by whatever is typed into it. Hence it is here and nowhere else. */}
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-sm)' }}>
          <SearchBar
            placeholder="Логин или имя"
            value={search}
            onChange={setSearch}
            aria-label="Поиск пользователей по логину или имени"
          />
        </div>

        {usersLoading ? (
          /* Skeletons, like every other list in the app. This was the
             one list that flashed a spinner on a cold fetch. */
          <SkeletonList count={3} />
        ) : usersFailed ? (
          <LoadError what="пользователей" onRetry={refetch} />
        ) : users.length === 0 && appliedSearch ? (
          /* A search that found nothing is not an app with no users in it: the two
             answers are different, and the wrong one invites adding a duplicate. */
          <EmptyState
            icon={Users}
            title="Никого не нашлось"
            description={`По запросу «${appliedSearch}» нет ни логина, ни имени`}
            actionLabel="Очистить поиск"
            onAction={() => setSearch('')}
          />
        ) : users.length === 0 ? (
          <EmptyState
            icon={Users}
            title="Пользователей пока нет"
            // A user created here is an ordinary one: the admin flag is not something this screen hands out,
            // so promising «и права» promised something it cannot give.
            description="Добавьте первого пользователя: у него будут свои питомцы, прав администратора не будет"
            actionLabel="Добавить пользователя"
            onAction={handleNewUser}
          />
        ) : (
          /* Pull-to-refresh, same as the other lists — this was the
             only one a user couldn't pull to reload. */
          <PullToRefresh
            onRefresh={async () => {
              hapticFeedback('medium');
              await refetch();
            }}
            headHeight={48}
          >
            <div className="safe-area-padding" style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--spacing-md)',
              marginTop: 'var(--spacing-sm)',
            }}>
              {(users as AdminUser[]).map((user) => {
                const isInactive = user.is_active === false;
                return (
                <SwipeableRow
                  key={user._id}
                  itemLabel={user.full_name || user.username}
                  leftAction={{
                    icon: <Pencil size={20} strokeWidth={2.4} />,
                    label: 'Изменить',
                    color: 'var(--app-accent)',
                    onTrigger: () => handleEdit(user),
                  }}
                  rightAction={user.username === currentUsername ? undefined : isInactive ? {
                    icon: <UserCheck size={20} strokeWidth={2.4} />,
                    label: 'Активировать',
                    color: 'var(--app-success-text)',
                    onTrigger: () => handleActivate(user.username),
                  } : {
                    icon: <UserX size={20} strokeWidth={2.4} />,
                    label: 'Деактивировать',
                    color: 'var(--app-danger-color)',
                    onTrigger: () => handleDelete(user.username),
                  }}
                  disabled={deactivateMutation.isPending || activateMutation.isPending}
                >
                {/* Tap opens the edit form (which also (de)activates);
                    swipe is the shortcut. A button, not a div with a click: a keyboard or a screen reader
                    could not open the card at all before. */}
                <button
                  type="button"
                  className="card-soft card-soft--interactive"
                  aria-label={`Изменить пользователя ${user.full_name || user.username}`}
                  onClick={() => handleEdit(user)}
                  style={{ padding: 16, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12, width: '100%', textAlign: 'left', font: 'inherit', color: 'inherit' }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    marginBottom: 'var(--spacing-md)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    flexWrap: 'wrap',
                  }}>
                    <span style={{
                      fontWeight: 500,
                      fontSize: 'var(--text-md)',
                      fontFamily: 'var(--font-display)',
                      color: 'var(--app-text-primary)',
                    }}>
                      {user.username}
                    </span>
                    {isInactive && (
                      <span
                        className="chip"
                        style={{ background: 'var(--app-danger-soft)', color: 'var(--app-danger-text)' }}
                      >
                        Деактивирован
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {user.full_name && (
                      <span style={{ fontSize: 'var(--text-sm)', color: 'var(--app-text-primary)' }}>{user.full_name}</span>
                    )}
                    {user.email && (
                      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)' }}>{user.email}</span>
                    )}
                    {/* An email set by someone else is never confirmed: only its owner can confirm it, from their
                        own screen. Said here, because otherwise the admin sees a mail and assumes it works. */}
                    {user.email && user.email_verified === false && (
                      <span
                        className="chip"
                        style={{ background: 'var(--app-accent-soft)', color: 'var(--app-accent-deep)', alignSelf: 'flex-start' }}
                      >
                        Не подтверждена
                      </span>
                    )}
                    <div style={{ marginTop: 'var(--spacing-sm)', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                      {user.created_at && (
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-tertiary)' }}>
                          {/* Raw "2026-09-20 07:40" was the only bare
                              timestamp in the UI; everything else speaks
                              in relative dates. */}
                          Создан {formatRelativeDate(user.created_at)}
                        </span>
                      )}
                    </div>
                  </div>
                  </div>
                  <CardChevron />
                </button>
                </SwipeableRow>
                );
              })}

              {/* Pages, only when there is more than one to be on. The count is of the search when one is typed,
                  so «найдено 3» is not read as the size of the whole list. */}
              {lastPage > 1 && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 'var(--spacing-sm)',
                  marginTop: 'var(--spacing-sm)',
                }}>
                  <Button
                    size="small"
                    fill="outline"
                    color="primary"
                    disabled={page <= 1 || isFetching}
                    onClick={() => { hapticFeedback('light'); setPage((p) => Math.max(1, p - 1)); }}
                  >
                    Назад
                  </Button>
                  <span style={{ fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
                    {appliedSearch ? 'Найдено' : 'Всего'} {total}, стр. {page} из {lastPage}
                  </span>
                  <Button
                    size="small"
                    fill="outline"
                    color="primary"
                    disabled={page >= lastPage || isFetching}
                    onClick={() => { hapticFeedback('light'); setPage((p) => p + 1); }}
                  >
                    Вперёд
                  </Button>
                </div>
              )}
            </div>
          </PullToRefresh>
        )}
      </div>

      {/* A user is added from the bottom right, as everything else in the app. */}
      {users.length > 0 && <Fab label="Добавить пользователя" onClick={handleNewUser} />}

      <Dialog
        visible={deleteDialog.visible}
        title="Деактивация пользователя"
        content={deleteDialog.username
          // The server ends every open session of that account (revoke_user_sessions), so the question says so:
          // otherwise a person is told «потеряет доступ» and their phone keeps working until the token expires.
          ? `Пользователь «${deleteDialog.username}» потеряет доступ к аккаунту и выйдет из него на всех устройствах, где сейчас открыт. Его можно будет активировать обратно в любой момент`
          : ''}
        onClose={() => setDeleteDialog(prev => ({ ...prev, visible: false }))}
        afterClose={() => setDeleteDialog({ visible: false, username: null })}
        actions={[
          {
            key: 'delete',
            text: 'Деактивировать',
            danger: true,
            onClick: () => {
              if (deleteDialog.username) {
                deactivateMutation.mutate(deleteDialog.username);
              }
              setDeleteDialog(prev => ({ ...prev, visible: false }));
            },
          },
          {
            key: 'cancel',
            text: 'Отмена',
            onClick: () => setDeleteDialog(prev => ({ ...prev, visible: false })),
          },
        ]}
      />
    </div>
  );
}

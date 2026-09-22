import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Dialog, PullToRefresh } from 'antd-mobile';
import { Pencil, UserX, UserCheck, Users } from 'lucide-react';
import { useAdmin } from '../hooks/useAdmin';
import { usersService, type User } from '../services/users.service';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SkeletonList } from '../components/Skeletons';
import { hapticFeedback } from '../utils/haptic';
import { SwipeableRow } from '../components/SwipeableRow';
import { EmptyState } from '../components/EmptyState';
import { formatRelativeDate } from '../utils/relativeTime';
import { getApiErrorMessage } from '../utils/apiError';

export function AdminPanel() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isAdmin, isLoading: isAdminLoading } = useAdmin();
  // State for alert messages
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const { data: users = [], isLoading: usersLoading, refetch } = useQuery({
    queryKey: ['users'],
    queryFn: () => usersService.getUsers(),
    enabled: isAdmin,
  });


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
      setError(getApiErrorMessage(err, 'Ошибка при деактивации пользователя'));
    },
  });

  const activateMutation = useMutation({
    mutationFn: (username: string) => usersService.updateUser(username, { is_active: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setSuccess('Пользователь активирован');
      setTimeout(() => setSuccess(null), 3000);
    },
    onError: (err: unknown) => {
      setError(getApiErrorMessage(err, 'Ошибка при активации пользователя'));
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

  if (!isAdmin) {
    return (
      <div style={{
        minHeight: '100vh',
        margin: '0 auto',
        paddingTop: '60px',
        paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
        paddingLeft: 'max(16px, env(safe-area-inset-left))',
        paddingRight: 'max(16px, env(safe-area-inset-right))',
        color: 'var(--app-text-color)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '32px' }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: '20px', margin: 0 }}>Админ-панель</h2>
        </div>
        <div style={{ marginTop: '16px' }}>
          <Alert type="error" message="У вас нет прав доступа к админ-панели" />
        </div>
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
          <h2 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Админ-панель</h2>
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

        <div className="safe-area-padding" style={{
          marginBottom: 'var(--spacing-lg)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          {/* Same .section-header as Settings, so the admin screen reads
              as part of the app rather than a bare CRUD table. */}
          <h3 className="section-header" style={{ fontSize: 'var(--text-lg)' }}>Пользователи</h3>
          {/* Flat copper, like every other primary action in the app.
              The brand gradient is reserved for the wordmark and the
              single sign-in button on the login screen; using it here
              made this the only gradient button inside the app shell. */}
          <button
            type="button"
            onClick={handleNewUser}
            style={{
              background: 'var(--app-primary-color)',
              border: 'none',
              borderRadius: '999px',
              color: '#FFFFFF',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              padding: '7px 16px',
              cursor: 'pointer',
            }}
          >
            + Добавить
          </button>
        </div>

        {usersLoading ? (
          /* Skeletons, like every other list in the app. This was the
             one list that flashed a spinner on a cold fetch. */
          <SkeletonList count={3} />
        ) : users.length === 0 ? (
          <EmptyState
            icon={Users}
            title="Пользователей пока нет"
            description="Добавьте первого пользователя — у каждого будут свои питомцы и права."
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
              {users.map((user) => {
                const isInactive = user.is_active === false;
                return (
                <SwipeableRow
                  key={user._id}
                  leftAction={{
                    icon: <Pencil size={20} strokeWidth={2.4} />,
                    label: 'Изменить',
                    color: 'var(--app-accent)',
                    onTrigger: () => handleEdit(user),
                  }}
                  rightAction={isInactive ? {
                    icon: <UserCheck size={20} strokeWidth={2.4} />,
                    label: 'Активировать',
                    color: 'var(--app-success-color)',
                    onTrigger: () => handleActivate(user.username),
                  } : {
                    icon: <UserX size={20} strokeWidth={2.4} />,
                    label: 'Деактивировать',
                    color: 'var(--app-danger-color)',
                    onTrigger: () => handleDelete(user.username),
                  }}
                  disabled={deactivateMutation.isPending || activateMutation.isPending}
                >
                {/* Editing and deactivating/activating are swipe actions.
                    No .tap-ripple here on purpose: the row has no tap
                    action, so a press animation would promise something
                    that never happens. */}
                <div
                  className="card-soft card-soft--interactive"
                  style={{ padding: 16 }}
                >
                  <div style={{
                    marginBottom: 10,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    flexWrap: 'wrap',
                  }}>
                    <span style={{
                      fontWeight: 600,
                      fontSize: 16,
                      fontFamily: 'var(--font-display)',
                      color: 'var(--app-text-primary)',
                    }}>
                      {user.username}
                    </span>
                    {isInactive && (
                      <span
                        className="chip"
                        style={{ background: 'var(--app-danger-soft, rgba(255,69,58,0.1))', color: 'var(--app-danger-color)' }}
                      >
                        Деактивирован
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {user.full_name && (
                      <span style={{ fontSize: 14, color: 'var(--app-text-primary)' }}>{user.full_name}</span>
                    )}
                    {user.email && (
                      <span style={{ fontSize: 12, color: 'var(--app-text-secondary)' }}>{user.email}</span>
                    )}
                    <div style={{ marginTop: 6, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                      {user.created_at && (
                        <span style={{ fontSize: 12, color: 'var(--app-text-tertiary)' }}>
                          {/* Raw "2026-09-20 07:40" was the only bare
                              timestamp in the UI; everything else speaks
                              in relative dates. */}
                          Создан {formatRelativeDate(user.created_at)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                </SwipeableRow>
                );
              })}
            </div>
          </PullToRefresh>
        )}
      </div>

      <Dialog
        visible={deleteDialog.visible}
        title="Деактивация пользователя"
        content={deleteDialog.username
          ? `Пользователь "${deleteDialog.username}" потеряет доступ к аккаунту. Его можно будет активировать обратно в любой момент.`
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

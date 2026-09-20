import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Dialog } from 'antd-mobile';
import { Pencil, Trash2, Users } from 'lucide-react';
import { useAdmin } from '../hooks/useAdmin';
import { usersService, type User } from '../services/users.service';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { hapticFeedback } from '../utils/haptic';
import { SwipeableRow } from '../components/SwipeableRow';
import { EmptyState } from '../components/EmptyState';
import { formatRelativeDate } from '../utils/relativeTime';

/**
 * A horizontal drag can still end with a synthetic click on some
 * browsers. Remember where the pointer went down and ignore anything
 * that travelled far enough to have been a swipe, so swipe-to-delete
 * never doubles as tap-to-edit.
 */
const TAP_SLOP_PX = 8;

export function AdminPanel() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isAdmin, isLoading: isAdminLoading } = useAdmin();
  // State for alert messages
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const tapOrigin = useRef<{ x: number; y: number } | null>(null);

  const { data: users = [], isLoading: usersLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => usersService.getUsers(),
    enabled: isAdmin,
  });


  const deleteUserMutation = useMutation({
    mutationFn: (username: string) => usersService.deleteUser(username),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setSuccess('Пользователь успешно удален');
      setTimeout(() => setSuccess(null), 3000);
    },
    onError: (err: any) => {
      setError(err.response?.data?.error || 'Ошибка при удалении пользователя');
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
          {/* antd-mobile's color="primary" paints this its own blue,
              which was the one non-brand surface in the app. Use the
              same copper gradient as every other primary action. */}
          <button
            type="button"
            onClick={handleNewUser}
            style={{
              background: 'var(--app-brand-gradient)',
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
          <LoadingSpinner fullscreen={false} />
        ) : (
          <div className="safe-area-padding" style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--spacing-md)',
            marginTop: 'var(--spacing-sm)',
          }}>
            {users.length === 0 ? (
              <EmptyState
                icon={Users}
                title="Пользователей пока нет"
                description="Добавьте первого пользователя — у каждого будут свои питомцы и права."
              />
            ) : (
              users.map((user) => (
                <SwipeableRow
                  key={user._id}
                  leftAction={{
                    icon: <Pencil size={20} strokeWidth={2.4} />,
                    label: 'Изменить',
                    color: 'var(--app-accent)',
                    onTrigger: () => handleEdit(user),
                  }}
                  rightAction={{
                    icon: <Trash2 size={20} strokeWidth={2.4} />,
                    label: 'Удалить',
                    color: 'var(--app-danger-color)',
                    onTrigger: () => handleDelete(user.username),
                  }}
                  disabled={deleteUserMutation.isPending}
                >
                {/* Tapping the row opens the editor — the same action the
                    left swipe commits. The card already carried
                    .tap-ripple, so a press animated and then resolved
                    to nothing; and without --interactive it lacked the
                    press/hover feedback every other card in the app has. */}
                <div
                  className="card-soft card-soft--interactive tap-ripple"
                  style={{ padding: 16, cursor: 'pointer' }}
                  role="button"
                  tabIndex={0}
                  aria-label={`Изменить пользователя ${user.username}`}
                  onPointerDown={(e) => { tapOrigin.current = { x: e.clientX, y: e.clientY }; }}
                  onClick={(e) => {
                    const origin = tapOrigin.current;
                    tapOrigin.current = null;
                    if (origin && Math.hypot(e.clientX - origin.x, e.clientY - origin.y) > TAP_SLOP_PX) return;
                    handleEdit(user);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleEdit(user);
                    }
                  }}
                >
                  <div style={{
                    marginBottom: 10,
                  }}>
                    <span style={{
                      fontWeight: 600,
                      fontSize: 16,
                      fontFamily: 'var(--font-display)',
                      color: 'var(--app-text-primary)',
                    }}>
                      {user.username}
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {user.full_name && (
                      <span style={{ fontSize: 14, color: 'var(--app-text-primary)' }}>{user.full_name}</span>
                    )}
                    {user.email && (
                      <span style={{ fontSize: 12, color: 'var(--app-text-secondary)' }}>{user.email}</span>
                    )}
                    <div style={{ marginTop: 6, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                      <span
                        className="chip"
                        style={{
                          background: user.is_active !== false
                            ? 'rgba(52, 199, 89, 0.12)'
                            : 'rgba(255, 69, 58, 0.10)',
                          color: user.is_active !== false
                            ? 'var(--app-success-color)'
                            : 'var(--app-danger-color)',
                        }}
                      >
                        {user.is_active !== false ? 'Активен' : 'Неактивен'}
                      </span>
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
              ))
            )}
          </div>
        )}
      </div>

      <Dialog
        visible={deleteDialog.visible}
        title="Удаление пользователя"
        content={deleteDialog.username ? `Вы уверены, что хотите удалить пользователя "${deleteDialog.username}"?` : ''}
        onClose={() => setDeleteDialog(prev => ({ ...prev, visible: false }))}
        afterClose={() => setDeleteDialog({ visible: false, username: null })}
        actions={[
          {
            key: 'delete',
            text: 'Удалить',
            danger: true,
            onClick: () => {
              if (deleteDialog.username) {
                deleteUserMutation.mutate(deleteDialog.username);
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

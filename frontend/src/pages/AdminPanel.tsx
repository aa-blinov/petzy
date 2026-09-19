import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Dialog } from 'antd-mobile';
import { Pencil, Trash2 } from 'lucide-react';
import { useAdmin } from '../hooks/useAdmin';
import { usersService, type User } from '../services/users.service';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { hapticFeedback } from '../utils/haptic';

export function AdminPanel() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isAdmin, isLoading: isAdminLoading } = useAdmin();
  // State for alert messages
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

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
          <h3 style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--app-text-color)' }}>Пользователи</h3>
          <Button
            color="primary"
            size="small"
            onClick={handleNewUser}
            style={{ borderRadius: 'var(--radius-md)' }}
          >
            + Добавить
          </Button>
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
              <p style={{ color: 'var(--app-text-secondary)', padding: 'var(--spacing-md) var(--spacing-lg)' }}>Пользователи не найдены</p>
            ) : (
              users.map((user) => (
                <div
                  key={user._id}
                  className="card-soft tap-ripple"
                  style={{ padding: 16 }}
                >
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
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
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <button
                        type="button"
                        onClick={() => handleEdit(user)}
                        aria-label="Редактировать"
                        style={{
                          width: 32, height: 32, padding: 0,
                          border: 'none', borderRadius: 'var(--radius-md)',
                          background: 'transparent',
                          color: 'var(--app-text-secondary)',
                          cursor: 'pointer', display: 'grid', placeItems: 'center',
                        }}
                      >
                        <Pencil size={16} strokeWidth={2} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(user.username)}
                        disabled={deleteUserMutation.isPending}
                        aria-label="Удалить"
                        style={{
                          width: 32, height: 32, padding: 0,
                          border: '1px solid var(--app-danger-color)',
                          borderRadius: 'var(--radius-md)',
                          background: 'transparent',
                          color: 'var(--app-danger-color)',
                          cursor: deleteUserMutation.isPending ? 'not-allowed' : 'pointer',
                          opacity: deleteUserMutation.isPending ? 0.5 : 1,
                          display: 'grid', placeItems: 'center',
                        }}
                      >
                        <Trash2 size={16} strokeWidth={2} />
                      </button>
                    </div>
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
                          Создан: {user.created_at}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
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

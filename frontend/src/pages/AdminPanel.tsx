import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Modal, Tag } from 'antd-mobile';
import { EditSOutline, DeleteOutline } from 'antd-mobile-icons';
import { useAdmin } from '../hooks/useAdmin';
import { useTheme } from '../hooks/useTheme';
import { usersService, type User } from '../services/users.service';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';

export function AdminPanel() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isAdmin, isLoading: isAdminLoading } = useAdmin();
  const { theme } = useTheme();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Determine if dark theme is active
  const isDark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

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

  const handleDelete = (username: string) => {
    Modal.confirm({
      content: `Вы уверены, что хотите удалить пользователя "${username}"?`,
      onConfirm: () => {
        deleteUserMutation.mutate(username);
      },
    });
  };

  const handleEdit = (user: User) => {
    navigate(`/admin/users/${user.username}/edit`);
  };

  const handleNewUser = () => {
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
    <div style={{ 
      minHeight: '100vh',
      backgroundColor: 'var(--app-page-background)',
      paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
      paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
      color: 'var(--app-text-color)'
    }}>
      <div style={{ 
        maxWidth: '800px', 
        margin: '0 auto'
      }}>
        <div style={{ 
          marginBottom: '16px', 
          paddingLeft: 'max(16px, env(safe-area-inset-left))',
          paddingRight: 'max(16px, env(safe-area-inset-right))'
        }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: '24px', fontWeight: 600, margin: 0 }}>Админ-панель</h2>
        </div>

        {error && (
          <div style={{ paddingBottom: '16px', paddingLeft: 'max(16px, env(safe-area-inset-left))', paddingRight: 'max(16px, env(safe-area-inset-right))' }}>
            <Alert type="error" message={error} onClose={() => setError(null)} />
          </div>
        )}
        {success && (
          <div style={{ paddingBottom: '16px', paddingLeft: 'max(16px, env(safe-area-inset-left))', paddingRight: 'max(16px, env(safe-area-inset-right))' }}>
            <Alert type="success" message={success} onClose={() => setSuccess(null)} />
          </div>
        )}

        <div style={{ 
          paddingLeft: 'max(16px, env(safe-area-inset-left))',
          paddingRight: 'max(16px, env(safe-area-inset-right))',
          marginBottom: '16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 600, color: 'var(--app-text-color)' }}>Пользователи</h3>
          <Button
            color="primary"
            size="small"
            onClick={handleNewUser}
          >
            + Добавить
          </Button>
        </div>

        {usersLoading ? (
          <LoadingSpinner />
        ) : (
          <div style={{ 
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            marginTop: '8px',
            paddingLeft: 'max(16px, env(safe-area-inset-left))',
            paddingRight: 'max(16px, env(safe-area-inset-right))'
          }}>
            {users.length === 0 ? (
              <p style={{ color: 'var(--app-text-secondary)', padding: '12px 16px' }}>Пользователи не найдены</p>
            ) : (
              users.map((user) => (
                <Card
                  key={user._id}
                  style={{
                    borderRadius: '12px',
                    border: 'none',
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
                  }}
                >
                  <div style={{ padding: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                      <span style={{ fontWeight: 600, fontSize: '16px' }}>{user.username}</span>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <Button
                          size="mini"
                          fill="outline"
                          onClick={() => handleEdit(user)}
                          style={{
                            '--text-color': isDark ? '#FFFFFF' : '#000000',
                            '--border-color': isDark ? 'rgba(255, 255, 255, 0.5)' : 'rgba(0, 0, 0, 0.15)',
                            backgroundColor: 'transparent',
                          } as React.CSSProperties}
                        >
                          <EditSOutline style={{ color: isDark ? '#FFFFFF' : '#000000', fontSize: '16px' }} />
                        </Button>
                        <Button
                          size="mini"
                          color="danger"
                          fill="outline"
                          onClick={() => handleDelete(user.username)}
                          disabled={deleteUserMutation.isPending}
                        >
                          <DeleteOutline />
                        </Button>
                      </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {user.full_name && <span>{user.full_name}</span>}
                      {user.email && <span style={{ fontSize: '12px', color: 'var(--adm-color-weak)' }}>{user.email}</span>}
                      <div style={{ marginTop: '4px' }}>
                        <Tag color={user.is_active !== false ? 'success' : 'danger'}>
                          {user.is_active !== false ? 'Активен' : 'Неактивен'}
                        </Tag>
                      </div>
                      {user.created_at && <span style={{ fontSize: '12px', color: 'var(--adm-color-weak)' }}>Создан: {user.created_at}</span>}
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

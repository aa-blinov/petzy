import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, List, Input, Modal, Switch, Toast, Form, Tag } from 'antd-mobile';
import { EditSOutline, DeleteOutline } from 'antd-mobile-icons';
import { useAdmin } from '../hooks/useAdmin';
import { usersService, type User, type UserCreate, type UserUpdate } from '../services/users.service';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';

export function AdminPanel() {
  const queryClient = useQueryClient();
  const { isAdmin, isLoading: isAdminLoading } = useAdmin();
  const [showUserForm, setShowUserForm] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const { data: users = [], isLoading: usersLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => usersService.getUsers(),
    enabled: isAdmin,
  });

  const createUserMutation = useMutation({
    mutationFn: (data: UserCreate) => usersService.createUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setShowUserForm(false);
      setSuccess('Пользователь успешно создан');
      setTimeout(() => setSuccess(null), 3000);
    },
    onError: (err: any) => {
      setError(err.response?.data?.error || 'Ошибка при создании пользователя');
    },
  });

  const updateUserMutation = useMutation({
    mutationFn: ({ username, data }: { username: string; data: UserUpdate }) =>
      usersService.updateUser(username, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setShowUserForm(false);
      setEditingUser(null);
      setSuccess('Пользователь успешно обновлен');
      setTimeout(() => setSuccess(null), 3000);
    },
    onError: (err: any) => {
      setError(err.response?.data?.error || 'Ошибка при обновлении пользователя');
    },
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
    setEditingUser(user);
    setShowUserForm(true);
  };

  const handleNewUser = () => {
    setEditingUser(null);
    setShowUserForm(true);
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
          <div style={{ marginTop: '8px' }}>
            {users.length === 0 ? (
              <p style={{ color: 'var(--app-text-secondary)', padding: '12px 16px' }}>Пользователи не найдены</p>
            ) : (
              <List mode="card">
                {users.map((user) => (
                  <List.Item
                    key={user._id}
                    extra={
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <Button
                          size="mini"
                          fill="outline"
                          onClick={() => handleEdit(user)}
                        >
                          <EditSOutline />
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
                    }
                    description={
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                        {user.full_name && <span>{user.full_name}</span>}
                        {user.email && <span style={{ fontSize: '12px' }}>{user.email}</span>}
                        <div style={{ marginTop: '4px' }}>
                          <Tag color={user.is_active !== false ? 'success' : 'danger'}>
                            {user.is_active !== false ? 'Активен' : 'Неактивен'}
                          </Tag>
                        </div>
                        {user.created_at && <span style={{ fontSize: '12px', color: '#999' }}>Создан: {user.created_at}</span>}
                      </div>
                    }
                  >
                    <span style={{ fontWeight: 600 }}>{user.username}</span>
                  </List.Item>
                ))}
              </List>
            )}
          </div>
        )}
      </div>

      <Modal
        visible={showUserForm}
        content={<UserForm
          user={editingUser}
          onClose={() => {
            setShowUserForm(false);
            setEditingUser(null);
          }}
          onSave={(data) => {
            if (editingUser) {
              updateUserMutation.mutate({ username: editingUser.username, data });
            } else {
              createUserMutation.mutate(data as UserCreate);
            }
          }}
          isLoading={createUserMutation.isPending || updateUserMutation.isPending}
        />}
        closeOnAction
        onClose={() => {
          setShowUserForm(false);
          setEditingUser(null);
        }}
      />
    </div>
  );
}

interface UserFormProps {
  user: User | null;
  onClose: () => void;
  onSave: (data: UserCreate | UserUpdate) => void;
  isLoading: boolean;
}

function UserForm({ user, onClose, onSave, isLoading }: UserFormProps) {
  const [username, setUsername] = useState(user?.username || '');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [isActive, setIsActive] = useState(user?.is_active !== false);

  const handleSubmit = () => {
    if (!user && (!username || !password)) {
      Toast.show({ icon: 'fail', content: 'Имя пользователя и пароль обязательны для нового пользователя' });
      return;
    }

    const data: UserCreate | UserUpdate = {
      ...(user ? {} : { username, password }),
      ...(fullName && { full_name: fullName }),
      ...(email && { email }),
      is_active: isActive,
    };

    onSave(data);
  };

  return (
    <div style={{ padding: '16px' }}>
      <h3 style={{ margin: 0, marginBottom: '24px', fontSize: '18px', fontWeight: 600, color: 'var(--app-text-color)' }}>
        {user ? 'Редактировать пользователя' : 'Создать пользователя'}
      </h3>
      
      <Form
        layout="vertical"
        onFinish={handleSubmit}
        footer={
          <div style={{ display: 'flex', gap: '8px', marginTop: '24px' }}>
            <Button
              type="submit"
              color="primary"
              block
              loading={isLoading}
              disabled={isLoading}
            >
              {isLoading ? 'Сохранение...' : 'Сохранить'}
            </Button>
            <Button
              type="button"
              fill="outline"
              block
              onClick={onClose}
              disabled={isLoading}
            >
              Отмена
            </Button>
          </div>
        }
      >
        {!user && (
          <Form.Item
            label="Имя пользователя *"
            name="username"
          >
            <Input
              type="text"
              value={username}
              onChange={(val) => setUsername(val)}
              disabled={isLoading}
              placeholder="Введите имя пользователя *"
              clearable
            />
          </Form.Item>
        )}
        
        {!user && (
          <Form.Item
            label="Пароль *"
            name="password"
          >
            <Input
              type="password"
              value={password}
              onChange={(val) => setPassword(val)}
              disabled={isLoading}
              placeholder="Введите пароль *"
              clearable
            />
          </Form.Item>
        )}
        
        <Form.Item
          label="Полное имя"
          name="fullName"
        >
          <Input
            type="text"
            value={fullName}
            onChange={(val) => setFullName(val)}
            disabled={isLoading}
            placeholder="Введите полное имя"
            clearable
          />
        </Form.Item>
        
        <Form.Item
          label="Email"
          name="email"
        >
          <Input
            type="email"
            value={email}
            onChange={(val) => setEmail(val)}
            disabled={isLoading}
            placeholder="Введите email"
            clearable
          />
        </Form.Item>
        
        <Form.Item
          label="Активен"
          name="isActive"
        >
          <Switch
            checked={isActive}
            onChange={(checked) => setIsActive(checked)}
            disabled={isLoading}
          />
        </Form.Item>
      </Form>
    </div>
  );
}

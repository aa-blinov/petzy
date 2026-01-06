import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Form, Input, Switch, Toast } from 'antd-mobile';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { usersService, type UserCreate, type UserUpdate } from '../services/users.service';

export function UserForm() {
  const navigate = useNavigate();
  const { username } = useParams<{ username: string }>();
  const isEditing = !!username;
  const queryClient = useQueryClient();

  // Fetch user data if editing
  const { data: user, isLoading: isLoadingUser } = useQuery({
    queryKey: ['users', username],
    queryFn: async () => {
      if (!username) return null;
      const users = await usersService.getUsers();
      return users.find(u => u.username === username) || null;
    },
    enabled: isEditing && !!username,
  });

  const [formUsername, setFormUsername] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [isActive, setIsActive] = useState(true);

  // Load user data into form when editing
  useEffect(() => {
    if (user) {
      setFormUsername(user.username);
      setPassword('');
      setFullName(user.full_name || '');
      setEmail(user.email || '');
      setIsActive(user.is_active !== false);
    } else if (!isEditing) {
      // Reset form for new user
      setFormUsername('');
      setPassword('');
      setFullName('');
      setEmail('');
      setIsActive(true);
    }
  }, [user, isEditing]);

  const createUserMutation = useMutation({
    mutationFn: (data: UserCreate) => usersService.createUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      Toast.show({ 
        icon: 'success', 
        content: 'Пользователь успешно создан',
        duration: 1500,
      });
      setTimeout(() => {
        navigate('/admin');
      }, 500);
    },
    onError: (err: any) => {
      const errorMessage = err.response?.data?.error || err.response?.data?.detail || 'Ошибка при создании пользователя';
      Toast.show({ 
        icon: 'fail', 
        content: errorMessage,
        duration: 2000,
      });
    },
  });

  const updateUserMutation = useMutation({
    mutationFn: ({ username, data }: { username: string; data: UserUpdate }) =>
      usersService.updateUser(username, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      Toast.show({ 
        icon: 'success', 
        content: 'Пользователь успешно обновлен',
        duration: 1500,
      });
      setTimeout(() => {
        navigate('/admin');
      }, 500);
    },
    onError: (err: any) => {
      const errorMessage = err.response?.data?.error || err.response?.data?.detail || 'Ошибка при обновлении пользователя';
      Toast.show({ 
        icon: 'fail', 
        content: errorMessage,
        duration: 2000,
      });
    },
  });

  const handleSubmit = () => {
    if (!isEditing && (!formUsername || !password)) {
      Toast.show({ 
        icon: 'fail', 
        content: 'Имя пользователя и пароль обязательны для нового пользователя',
        duration: 2000,
      });
      return;
    }

    const data: UserCreate | UserUpdate = {
      ...(isEditing ? {} : { username: formUsername, password }),
      ...(isEditing && password && password.trim() && { password: password.trim() }),
      ...(fullName && { full_name: fullName }),
      ...(email && { email }),
      is_active: isActive,
    };

    if (isEditing && username) {
      updateUserMutation.mutate({ username, data });
    } else {
      createUserMutation.mutate(data as UserCreate);
    }
  };

  if (isEditing && isLoadingUser) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
        paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
        backgroundColor: 'var(--app-page-background)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--app-text-color)'
      }}>
        Загрузка...
      </div>
    );
  }

  const isLoading = createUserMutation.isPending || updateUserMutation.isPending;

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
          paddingLeft: 'max(16px, env(safe-area-inset-left))', 
          paddingRight: 'max(16px, env(safe-area-inset-right))' 
        }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: '24px', fontWeight: 600, margin: 0 }}>
            {isEditing ? 'Редактировать пользователя' : 'Создать пользователя'}
          </h2>
        </div>

        <div style={{ 
          paddingLeft: 'max(16px, env(safe-area-inset-left))',
          paddingRight: 'max(16px, env(safe-area-inset-right))'
        }}>
          <Form
            layout="vertical"
            footer={
              <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
                <Button
                  onClick={() => navigate('/admin')}
                  style={{ flex: 1 }}
                >
                  Отмена
                </Button>
                <Button
                  color="primary"
                  onClick={handleSubmit}
                  loading={isLoading}
                  style={{ flex: 1 }}
                >
                  {isEditing ? 'Сохранить' : 'Создать'}
                </Button>
              </div>
            }
          >
            {!isEditing && (
              <Form.Item
                label="Имя пользователя *"
                name="username"
              >
                <Input
                  type="text"
                  value={formUsername}
                  onChange={(val) => setFormUsername(val)}
                  disabled={isLoading}
                  placeholder="Введите имя пользователя *"
                  clearable
                  autoComplete="username"
                />
              </Form.Item>
            )}
            
            {!isEditing ? (
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
                  autoComplete="new-password"
                />
              </Form.Item>
            ) : (
              <>
                {/* Hidden username field for password form accessibility */}
                <input
                  type="text"
                  value={user?.username || ''}
                  autoComplete="username"
                  readOnly
                  style={{ position: 'absolute', left: '-9999px', width: '1px', height: '1px', opacity: 0 }}
                  tabIndex={-1}
                  aria-hidden="true"
                />
                <Form.Item
                  label="Новый пароль"
                  name="password"
                >
                  <Input
                    type="password"
                    value={password}
                    onChange={(val) => setPassword(val)}
                    disabled={isLoading}
                    placeholder="Оставьте пустым, чтобы не менять пароль"
                    clearable
                    autoComplete="new-password"
                  />
                </Form.Item>
              </>
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
                autoComplete="name"
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
                autoComplete="email"
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
      </div>
    </div>
  );
}


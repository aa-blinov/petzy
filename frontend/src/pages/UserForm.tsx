import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Form, Input, Switch, Toast } from 'antd-mobile';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { usersService, type UserCreate, type UserUpdate } from '../services/users.service';
import { LoadingSpinner } from '../components/LoadingSpinner';

const userSchema = z.object({
  username: z.string().min(1, 'Имя пользователя обязательно'),
  password: z.string().optional(),
  full_name: z.string().optional(),
  email: z.string().email('Некорректный email').optional().or(z.literal('')),
  is_active: z.boolean(),
});

type UserFormData = z.infer<typeof userSchema>;

export function UserForm() {
  const navigate = useNavigate();
  const { username } = useParams<{ username: string }>();
  const isEditing = !!username;
  const queryClient = useQueryClient();

  const { control, handleSubmit, reset, formState: { isSubmitting } } = useForm<UserFormData>({
    resolver: zodResolver(userSchema),
    defaultValues: {
      username: '',
      password: '',
      full_name: '',
      email: '',
      is_active: true,
    }
  });

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

  // Load user data into form when editing
  useEffect(() => {
    if (user) {
      reset({
        username: user.username,
        password: '',
        full_name: user.full_name || '',
        email: user.email || '',
        is_active: user.is_active !== false,
      });
    } else if (!isEditing) {
      reset({
        username: '',
        password: '',
        full_name: '',
        email: '',
        is_active: true,
      });
    }
  }, [user, isEditing, reset]);

  const createUserMutation = useMutation({
    mutationFn: (data: UserCreate) => usersService.createUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      Toast.show({ icon: 'success', content: 'Пользователь успешно создан', duration: 1500 });
      setTimeout(() => navigate('/admin'), 500);
    },
    onError: (err: any) => {
      const errorMessage = err.response?.data?.error || err.response?.data?.detail || 'Ошибка при создании пользователя';
      Toast.show({ icon: 'fail', content: errorMessage, duration: 2000 });
    },
  });

  const updateUserMutation = useMutation({
    mutationFn: ({ username, data }: { username: string; data: UserUpdate }) =>
      usersService.updateUser(username, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      Toast.show({ icon: 'success', content: 'Пользователь успешно обновлен', duration: 1500 });
      setTimeout(() => navigate('/admin'), 500);
    },
    onError: (err: any) => {
      const errorMessage = err.response?.data?.error || err.response?.data?.detail || 'Ошибка при обновлении пользователя';
      Toast.show({ icon: 'fail', content: errorMessage, duration: 2000 });
    },
  });

  const onSubmit = (formData: UserFormData) => {
    if (!isEditing && !formData.password) {
      Toast.show({ icon: 'fail', content: 'Пароль обязателен для нового пользователя', duration: 2000 });
      return;
    }

    const data: UserCreate | UserUpdate = {
      ...(isEditing ? {} : { username: formData.username, password: formData.password || '' }),
      ...(isEditing && formData.password?.trim() && { password: formData.password.trim() }),
      full_name: formData.full_name || '',
      email: formData.email || '',
      is_active: formData.is_active,
    };

    if (isEditing && username) {
      updateUserMutation.mutate({ username, data });
    } else {
      createUserMutation.mutate(data as UserCreate);
    }
  };

  if (isEditing && isLoadingUser) {
    return <LoadingSpinner />;
  }

  const isLoading = isSubmitting || createUserMutation.isPending || updateUserMutation.isPending;

  return (
    <div style={{
      minHeight: '100vh', paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
      paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
      backgroundColor: 'var(--app-page-background)', color: 'var(--app-text-color)'
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ marginBottom: '16px', padding: '0 max(16px, env(safe-area-inset-left))' }}>
          <h2 style={{ fontSize: '24px', fontWeight: 600, margin: 0 }}>
            {isEditing ? 'Редактировать пользователя' : 'Создать пользователя'}
          </h2>
        </div>

        <div>
          <Form
            layout="horizontal"
            mode="card"
          >
            {!isEditing && (
              <Controller
                name="username"
                control={control}
                render={({ field, fieldState: { error } }) => (
                  <Form.Item label="Имя пользователя" required help={error?.message}>
                    <Input
                      {...field}
                      id="username"
                      placeholder="Введите имя пользователя"
                      clearable
                      autoComplete="username"
                      style={{ '--text-align': 'right' }}
                    />
                  </Form.Item>
                )}
              />
            )}

            <Controller
              name="password"
              control={control}
              render={({ field }) => (
                <>
                  {isEditing && (
                    <input
                      type="text"
                      value={username || ''}
                      autoComplete="username"
                      readOnly
                      style={{ position: 'absolute', left: '-9999px', width: '1px', height: '1px', opacity: 0 }}
                      tabIndex={-1}
                      aria-hidden="true"
                    />
                  )}
                  <Form.Item label={isEditing ? "Новый пароль" : "Пароль"} required={!isEditing}>
                    <Input
                      {...field}
                      id="password"
                      type="password"
                      placeholder={isEditing ? "Оставьте пустым" : "Введите пароль"}
                      clearable
                      autoComplete="new-password"
                      style={{ '--text-align': 'right' }}
                    />
                  </Form.Item>
                </>
              )}
            />

            <Controller
              name="full_name"
              control={control}
              render={({ field }) => (
                <Form.Item label="Полное имя">
                  <Input
                    {...field}
                    id="full_name"
                    placeholder="Введите полное имя"
                    clearable
                    autoComplete="name"
                    style={{ '--text-align': 'right' }}
                  />
                </Form.Item>
              )}
            />

            <Controller
              name="email"
              control={control}
              render={({ field, fieldState: { error } }) => (
                <Form.Item label="Email" help={error?.message}>
                  <Input
                    {...field}
                    id="email"
                    type="email"
                    placeholder="Введите email"
                    clearable
                    autoComplete="email"
                    style={{ '--text-align': 'right' }}
                  />
                </Form.Item>
              )}
            />

            <Controller
              name="is_active"
              control={control}
              render={({ field: { value, onChange } }) => (
                <Form.Item label="Активен">
                  <Switch
                    checked={value}
                    onChange={onChange}
                  />
                </Form.Item>
              )}
            />
          </Form>

          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            marginTop: '24px',
            paddingBottom: '24px',
            marginLeft: '12px',
            marginRight: '12px'
          }}>
            <button
              style={{ display: 'none' }}
              type="submit"
              onClick={(e) => { e.preventDefault(); handleSubmit(onSubmit)(); }}
            />
            <Button
              block
              color="primary"
              size="large"
              onClick={() => handleSubmit(onSubmit)()}
              loading={isLoading}
              style={{ borderRadius: '12px', fontWeight: 600 }}
            >
              {isEditing ? 'Сохранить' : 'Создать'}
            </Button>
            <Button
              block
              size="large"
              onClick={() => navigate('/admin')}
              style={{ borderRadius: '12px', fontWeight: 500 }}
            >
              Отмена
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}


import { useEffect } from 'react';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { useNavigate, useParams } from 'react-router-dom';
import { goBack } from '../utils/navigation';
import { Button, Form, Input } from 'antd-mobile';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { usersService, type UserCreate, type UserUpdate } from '../services/users.service';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SpinnerButton } from '../components/SpinnerButton';
import { FieldError } from '../components/FieldError';
import { onInvalidSubmit } from '../utils/formErrors';
import { FormDangerButton } from '../components/FormDangerButton';
import { useAuth } from '../hooks/useAuth';

// A new user needs a password; an edit leaves it blank to keep the old
// one. This was a toast in onSubmit, shown only once every other field
// passed.
const buildUserSchema = (isEditing: boolean) => z.object({
  username: z.string().min(1, 'Введите логин'),
  password: isEditing ? z.string().optional() : z.string().min(1, 'Придумайте пароль'),
  full_name: z.string().optional(),
  email: z.string().email('Проверьте email, например name@mail.ru').optional().or(z.literal('')),
});

type UserFormData = z.infer<ReturnType<typeof buildUserSchema>>;

export function UserForm() {
  const navigate = useNavigate();
  const { username } = useParams<{ username: string }>();
  const isEditing = !!username;
  const queryClient = useQueryClient();
  const { username: currentUsername } = useAuth();

  const { control, handleSubmit, reset, formState: { isSubmitting } } = useForm<UserFormData>({
    // onInvalidSubmit scrolls to and focuses the first error in page order;
    // RHF's own focus picked the first registered ref instead.
    shouldFocusError: false,
    resolver: zodResolver(buildUserSchema(isEditing)),
    defaultValues: {
      username: '',
      password: '',
      full_name: '',
      email: '',
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
      });
    } else if (!isEditing) {
      reset({
        username: '',
        password: '',
        full_name: '',
        email: '',
      });
    }
  }, [user, isEditing, reset]);

  const createUserMutation = useMutation({
    mutationFn: (data: UserCreate) => usersService.createUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      showToast.success('Пользователь создан');
      setTimeout(() => goBack(navigate, '/admin'), 500);
    },
    onError: (err: unknown) => {
      showToast.failure(getApiErrorMessage(err, 'Не удалось создать пользователя'));
    },
  });

  const setActive = useMutation({
    mutationFn: async (active: boolean) => {
      if (active) await usersService.updateUser(username!, { is_active: true });
      else await usersService.deleteUser(username!);
    },
    onSuccess: (_data, active) => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      showToast.success(active ? 'Пользователь активирован' : 'Пользователь деактивирован');
      goBack(navigate, '/admin');
    },
    onError: (err: unknown, active) => {
      showToast.failure(
        getApiErrorMessage(err, active ? 'Не удалось активировать пользователя' : 'Не удалось деактивировать пользователя'),
      );
    },
  });

  const updateUserMutation = useMutation({
    mutationFn: ({ username, data }: { username: string; data: UserUpdate }) =>
      usersService.updateUser(username, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      showToast.success('Пользователь обновлён');
      setTimeout(() => goBack(navigate, '/admin'), 500);
    },
    onError: (err: unknown) => {
      showToast.failure(getApiErrorMessage(err, 'Не удалось обновить пользователя'));
    },
  });

  const onSubmit = (formData: UserFormData) => {
    const data: UserCreate | UserUpdate = {
      ...(isEditing ? {} : { username: formData.username, password: formData.password || '' }),
      ...(isEditing && formData.password?.trim() && { password: formData.password.trim() }),
      full_name: formData.full_name || '',
      email: formData.email || '',
      // is_active is deliberately not sent. Create hardcodes it to true
      // server-side and update only writes it when present, so omitting
      // it leaves an existing account's state untouched.
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
          <h1 style={{ fontSize: '24px', fontWeight: 600, margin: 0 }}>
            {isEditing ? 'Редактировать пользователя' : 'Создать пользователя'}
          </h1>
        </div>

        <div>
          <Form
            layout="horizontal"
            mode="card"
            style={{
              '--prefix-width': '7em'
            } as React.CSSProperties}
          >
            <Form.Header>Учётные данные</Form.Header>
            {!isEditing && (
              <Controller
                name="username"
                control={control}
                render={({ field, fieldState: { error } }) => (
                  <Form.Item label="Логин" required description={error?.message ? <FieldError message={error.message} /> : undefined}>
                    <Input
                      {...field}
                      id="username"
                      placeholder="Введите имя пользователя"
                      clearable
                      autoComplete="username"
                    />
                  </Form.Item>
                )}
              />
            )}

            <Controller
              name="password"
              control={control}
              render={({ field, fieldState: { error } }) => (
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
                  <Form.Item
                    label={isEditing ? "Новый пароль" : "Пароль"}
                    required={!isEditing}
                    description={error?.message ? <FieldError message={error.message} /> : undefined}
                  >
                    <Input
                      {...field}
                      id="password"
                      type="password"
                      placeholder={isEditing ? "Оставьте пустым" : "Введите пароль"}
                      clearable
                      autoComplete="new-password"
                    />
                  </Form.Item>
                </>
              )}
            />

            <Form.Header>Профиль</Form.Header>

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
                  />
                </Form.Item>
              )}
            />

            <Controller
              name="email"
              control={control}
              render={({ field, fieldState: { error } }) => (
                <Form.Item label="Email" description={error?.message ? <FieldError message={error.message} /> : undefined}>
                  <Input
                    {...field}
                    id="email"
                    type="email"
                    placeholder="Введите email"
                    clearable
                    autoComplete="email"
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
              onClick={(e) => { e.preventDefault(); handleSubmit(onSubmit, onInvalidSubmit)(); }}
            />
            <SpinnerButton
              loading={isLoading}
              onClick={() => handleSubmit(onSubmit, onInvalidSubmit)()}
              style={{ borderRadius: '12px', fontWeight: 600 }}
            >
              {isEditing ? 'Сохранить' : 'Создать'}
            </SpinnerButton>
            <Button
              block
              size="large"
              onClick={() => goBack(navigate, '/admin')}
              style={{ borderRadius: '12px', fontWeight: 500 }}
            >
              Отмена
            </Button>
            {/* Users are never deleted, only deactivated (and back). Not
                your own account: the server refuses, and it would lock
                you out. */}
            {isEditing && user && user.username !== currentUsername && (user.is_active === false ? (
              <Button
                block
                size="large"
                fill="none"
                loading={setActive.isPending}
                onClick={() => setActive.mutate(true)}
                style={{ borderRadius: '12px', fontWeight: 500, color: 'var(--app-success-text)' }}
              >
                Активировать
              </Button>
            ) : (
              <FormDangerButton
                label="Деактивировать"
                confirmTitle="Деактивация пользователя"
                confirmContent={`Пользователь «${user.username}» потеряет доступ к аккаунту. Его можно будет активировать обратно в любой момент`}
                onConfirm={() => setActive.mutateAsync(false)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}


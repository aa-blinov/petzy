import { useState } from 'react';
import { showToast } from '../utils/toast';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { authService } from '../services/auth.service';
import { useAuth } from '../hooks/useAuth';
import { Button, Input, Form } from 'antd-mobile';
import { isAxiosError } from 'axios';
import { AuthShell } from '../components/AuthShell';

export function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  // useSession() forces isAuthenticated to false on this page (the login
  // screen must not fire the authenticated session probe), so it can't
  // tell us whether the visitor is actually already signed in. `username`
  // is the one signal still available here: with the probe disabled it
  // falls back to the last-known-signed-in name kept in localStorage — set
  // on login, cleared on logout or a real 401. A bookmark or the back
  // button landing here with that name still present means the httpOnly
  // cookies are very likely still good, so send them straight to the
  // dashboard instead of making them look at (and possibly resubmit) the
  // login form. If the cookies actually did expire, ProtectedRoute's own
  // probe on "/" finds out and bounces back here — this is an optimistic
  // redirect, not a claim that the session is confirmed valid.
  const { login, username: storedUsername } = useAuth();
  const navigate = useNavigate();
  // Offered only while sign-up is open (REGISTRATION_ENABLED).
  const { data: status } = useQuery({
    queryKey: ['registration-status'],
    queryFn: () => authService.registrationStatus(),
    retry: false,
  });

  if (storedUsername) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async () => {
    if (!username.trim()) {
      showToast.failure('Введите логин');
      return;
    }
    if (!password) {
      showToast.failure('Введите пароль');
      return;
    }

    setIsLoading(true);
    try {
      // login() clears the query cache and releases the interceptor's
      // sign-out latch, so the protected pages mount against an empty
      // cache and re-probe the (now valid) session. The old 100 ms
      // sleep waited for cookies that the browser had already applied
      // when the response headers arrived.
      await login({ username: username.trim(), password });
      navigate('/', { replace: true });
    } catch (err) {
      let errorMessage = 'Не удалось войти. Проверьте соединение или логин и пароль';
      if (isAxiosError<{ error?: string; message?: string }>(err)) {
        const status = err.response?.status;
        const data = err.response?.data;
        if (status === 422) errorMessage = data?.error || data?.message || 'Неверные данные';
        else if (status === 401) errorMessage = data?.error || data?.message || 'Неверный логин или пароль';
        else if (status === 429) errorMessage = data?.error || data?.message || 'Слишком много попыток. Попробуйте позже';
        else if (err.message === 'Network Error') errorMessage = 'Ошибка сети. Проверьте, работает ли сервер';
        else errorMessage = data?.error || data?.message || err.message || errorMessage;
      } else if (err instanceof Error && err.message) {
        errorMessage = err.message;
      }

      showToast.failure(errorMessage);
      console.error('Login error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthShell>
          <Form
            layout="vertical"
            onFinish={handleSubmit}
            footer={
              <>
              <Button
                color="primary"
                block
                size="large"
                loading={isLoading}
                disabled={isLoading}
                type="submit"
                style={{
                  marginTop: 8,
                  // The brand gradient, deepened so the white label reads
                  // (the wordmark above keeps the lighter original).
                  background: 'var(--app-cta-gradient)',
                  border: 'none',
                }}
              >
                {isLoading ? 'Вход...' : 'Войти'}
              </Button>
              <p style={{ margin: 'var(--spacing-md) 0 0', fontSize: 'var(--text-sm)', textAlign: 'center' }}>
                <Link to="/forgot-password" style={{ color: 'var(--app-accent-deep)', fontWeight: 600 }}>
                  Забыли пароль?
                </Link>
              </p>
              {status?.open && (
                <p style={{ margin: 'var(--spacing-sm) 0 0', fontSize: 'var(--text-sm)', textAlign: 'center', color: 'var(--app-text-secondary)' }}>
                  Нет аккаунта?{' '}
                  <Link to="/register" style={{ color: 'var(--app-accent-deep)', fontWeight: 600 }}>
                    Создать
                  </Link>
                </p>
              )}
              </>
            }
          >
            <Form.Item
              label={
                <span style={{ color: 'var(--app-text-primary)', fontWeight: 500 }}>
                  Логин
                </span>
              }
              name="username"
            >
              <Input
                placeholder="Введите логин"
                value={username}
                onChange={(val) => setUsername(val)}
                disabled={isLoading}
                clearable
                autoComplete="username"
              />
            </Form.Item>
            <Form.Item
              label={
                <span style={{ color: 'var(--app-text-primary)', fontWeight: 500 }}>
                  Пароль
                </span>
              }
              name="password"
            >
              <Input
                type="password"
                placeholder="Введите пароль"
                value={password}
                onChange={(val) => setPassword(val)}
                disabled={isLoading}
                clearable
                autoComplete="current-password"
              />
            </Form.Item>
          </Form>
    </AuthShell>
  );
}

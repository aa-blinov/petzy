import { useState } from 'react';
import { showToast } from '../utils/toast';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Button, Input, Form } from 'antd-mobile';
import { isAxiosError } from 'axios';

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

  if (storedUsername) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async () => {
    if (!username.trim()) {
      showToast.failure('Введите имя пользователя');
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
      let errorMessage = 'Ошибка входа. Проверьте соединение или учетные данные.';
      if (isAxiosError<{ error?: string; message?: string }>(err)) {
        const status = err.response?.status;
        const data = err.response?.data;
        if (status === 422) errorMessage = data?.error || data?.message || 'Неверные данные.';
        else if (status === 401) errorMessage = data?.error || data?.message || 'Неверный логин или пароль.';
        else if (status === 429) errorMessage = data?.error || data?.message || 'Слишком много попыток. Попробуйте позже.';
        else if (err.message === 'Network Error') errorMessage = 'Ошибка сети. Проверьте, запущен ли бэкенд.';
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
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '16px',
      backgroundColor: 'var(--app-page-background)',
      paddingTop: 'env(safe-area-inset-top)',
      paddingBottom: 'env(safe-area-inset-bottom)',
    }}>
      <div style={{ width: '100%', maxWidth: '400px' }}>
        {/* Stylized wordmark — gradient copper fill, no icon, no subtitle
           so the brand reads as the literal name, not a logo.

           Same face as the navbar wordmark (--app-font-bubble, DynaPuff):
           this and the navbar are the only two places the brand name is
           set, so they have to be the same letterform or the login
           screen reads as a different product. Tracking is kept near the
           navbar's (-0.5px at 28px ≈ -0.018em) — DynaPuff's rounded
           terminals collide under the -0.04em the display face took. */}
        <h1
          style={{
            textAlign: 'center',
            margin: '0 0 32px',
            fontFamily: 'var(--app-font-bubble)',
            fontSize: 56,
            fontWeight: 700,
            letterSpacing: '-0.02em',
            lineHeight: 1,
            background: 'var(--app-brand-gradient)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            color: 'var(--app-accent)',
          }}
        >
          Petzy
        </h1>

        {/* Form card.
            spellCheck / autoCapitalize / autoCorrect sit here rather
            than on the Input: antd-mobile's Input only forwards a
            whitelist of native props, and these three are inherited by
            descendants anyway. A username is not prose — spellcheck
            drew a red squiggle under it (and under nothing else, so the
            two fields read as mismatched), and auto-capitalisation on
            mobile turns "admin" into "Admin" against a case-sensitive
            lookup. */}
        <div
          className="card-soft"
          style={{ padding: '28px 24px' }}
          spellCheck={false}
          autoCapitalize="none"
          autoCorrect="off"
        >
          <Form
            layout="vertical"
            onFinish={handleSubmit}
            footer={
              <Button
                color="primary"
                block
                size="large"
                loading={isLoading}
                disabled={isLoading}
                type="submit"
                style={{
                  marginTop: 8,
                  // Brand gradient — matches the Petzy wordmark above so
                  // the two copper surfaces on this screen read as the
                  // same identity, not two competing ones.
                  background: 'var(--app-brand-gradient)',
                  border: 'none',
                }}
              >
                {isLoading ? 'Вход...' : 'Войти'}
              </Button>
            }
          >
            <Form.Item
              label={
                <span style={{ color: 'var(--app-text-primary)', fontWeight: 500 }}>
                  Имя пользователя
                </span>
              }
              name="username"
            >
              <Input
                placeholder="Введите имя пользователя"
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
        </div>
      </div>
    </div>
  );
}

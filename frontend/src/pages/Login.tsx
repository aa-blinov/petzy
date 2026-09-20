import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Button, Input, Toast, Form } from 'antd-mobile';

export function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async () => {
    if (!username.trim()) {
      Toast.show({ icon: 'fail', content: 'Введите имя пользователя' });
      return;
    }
    if (!password) {
      Toast.show({ icon: 'fail', content: 'Введите пароль' });
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
    } catch (err: any) {
      let errorMessage = 'Ошибка входа. Проверьте соединение или учетные данные.';
      if (err.response) {
        const status = err.response.status;
        const data = err.response.data;
        if (status === 422) errorMessage = data?.error || data?.message || 'Неверные данные.';
        else if (status === 401) errorMessage = data?.error || data?.message || 'Неверный логин или пароль.';
        else if (status === 429) errorMessage = data?.error || data?.message || 'Слишком много попыток. Попробуйте позже.';
        else errorMessage = data?.error || data?.message || errorMessage;
      } else if (err.message === 'Network Error') {
        errorMessage = 'Ошибка сети. Проверьте, запущен ли бэкенд.';
      } else if (err.message) {
        errorMessage = err.message;
      }

      Toast.show({ icon: 'fail', content: errorMessage, duration: 2000 });
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

        {/* Form card */}
        <div className="card-soft" style={{ padding: '28px 24px' }}>
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

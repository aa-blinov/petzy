import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Button, Input, Toast, Form } from 'antd-mobile';
import { PawPrint } from 'lucide-react';

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
      await login({ username: username.trim(), password });
      await new Promise(resolve => setTimeout(resolve, 100));
      navigate('/');
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
        {/* Brand block */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div
            aria-hidden
            style={{
              width: 64,
              height: 64,
              borderRadius: 20,
              margin: '0 auto 16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FFFFFF',
              background: 'var(--app-brand-gradient)',
              boxShadow: '0 8px 24px rgba(196, 106, 63, 0.35)',
            }}
          >
            <PawPrint size={32} strokeWidth={2} style={{ display: 'block' }} />
          </div>
          <h1
            className="display-headline"
            style={{
              fontSize: 36,
              fontWeight: 700,
              letterSpacing: '-0.02em',
              margin: 0,
              color: 'var(--app-text-primary)',
            }}
          >
            Petzy
          </h1>
          <p
            style={{
              marginTop: 8,
              fontSize: 'var(--text-sm)',
              color: 'var(--app-text-secondary)',
            }}
          >
            Здоровье вашего питомца — в одном месте
          </p>
        </div>

        {/* Form card */}
        <div className="card-soft" style={{ padding: '28px 24px' }}>
          <Form
            layout="vertical"
            onFinish={handleSubmit}
            footer={
              <Button
                color="primary"
                block
                loading={isLoading}
                disabled={isLoading}
                type="submit"
                style={{ marginTop: 8 }}
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

          {/* Seed credentials hint — dev convenience. Hidden in prod by env. */}
          {import.meta.env.DEV && (
            <div
              style={{
                marginTop: 16,
                padding: '10px 12px',
                background: 'var(--app-accent-soft)',
                borderRadius: 'var(--radius-md)',
                fontSize: 'var(--text-xs)',
                color: 'var(--app-accent-deep)',
                lineHeight: 1.5,
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 2 }}>Dev-учётка:</div>
              <code style={{ fontFamily: 'ui-monospace, SFMono-Regular, monospace' }}>
                admin / test1234
              </code>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

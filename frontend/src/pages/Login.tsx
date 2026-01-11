import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Button, Input, Toast, Card, Form } from 'antd-mobile';

export function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async () => {

    // Frontend validation
    if (!username.trim()) {
      Toast.show({
        icon: 'fail',
        content: 'Введите имя пользователя',
      });
      return;
    }

    if (!password) {
      Toast.show({
        icon: 'fail',
        content: 'Введите пароль',
      });
      return;
    }

    setIsLoading(true);

    try {
      await login({ username: username.trim(), password });
      // Wait a bit to ensure cookies are set
      await new Promise(resolve => setTimeout(resolve, 100));
      // Navigate to dashboard
      navigate('/');
    } catch (err: any) {
      // Extract error message from response
      let errorMessage = 'Ошибка входа. Проверьте соединение или учетные данные.';

      if (err.response) {
        const status = err.response.status;
        const data = err.response.data;

        if (status === 422) {
          // Validation error
          errorMessage = data?.error || data?.message || 'Неверные данные. Проверьте введенные данные.';
        } else if (status === 401) {
          // Unauthorized
          errorMessage = data?.error || data?.message || 'Неверный логин или пароль.';
        } else if (status === 429) {
          // Rate limit
          errorMessage = data?.error || data?.message || 'Слишком много попыток. Попробуйте позже.';
        } else {
          errorMessage = data?.error || data?.message || errorMessage;
        }
      } else if (err.message) {
        if (err.message === 'Network Error') {
          errorMessage = 'Ошибка сети. Проверьте, запущен ли бэкенд.';
        } else {
          errorMessage = err.message;
        }
      }

      Toast.show({
        icon: 'fail',
        content: errorMessage,
        duration: 2000,
      });
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
      paddingBottom: 'env(safe-area-inset-bottom)'
    }}>
      <div style={{ width: '100%', maxWidth: '400px' }}>
        <Card style={{ padding: '32px', backgroundColor: 'var(--app-card-background)' }}>
          <div
            style={{
              fontFamily: 'var(--app-font-bubble)',
              fontSize: '48px',
              fontWeight: 700,
              background: 'var(--app-brand-gradient)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              textAlign: 'center',
              marginBottom: '16px',
              filter: 'drop-shadow(var(--app-shadow))'
            }}
          >
            Petzy
          </div>
          <p style={{
            textAlign: 'center',
            marginBottom: '32px',
            fontSize: '1rem',
            color: 'var(--app-text-secondary)',
            fontWeight: 400
          }}>
            Вход в систему
          </p>

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
              >
                {isLoading ? 'Вход...' : 'Войти'}
              </Button>
            }
          >
            <Form.Item
              label="Имя пользователя"
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
              label="Пароль"
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
        </Card>
      </div>
    </div>
  );
}


import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button, Form, Input } from 'antd-mobile';
import { authService } from '../services/auth.service';
import { AuthShell } from '../components/AuthShell';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';

const linkStyle = { color: 'var(--app-accent-deep)', fontWeight: 600 } as const;

/** «Забыли пароль?»: a link to set a new one, sent to the confirmed email. */
export function ForgotPassword() {
  const [login, setLogin] = useState('');
  const [sent, setSent] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const status = useQuery({ queryKey: ['registration-status'], queryFn: () => authService.registrationStatus() });

  const submit = async () => {
    if (!login.trim()) {
      showToast.failure('Введите логин или почту');
      return;
    }
    setIsLoading(true);
    try {
      setSent(await authService.forgotPassword(login.trim()));
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось отправить запрос. Проверьте соединение'));
    } finally {
      setIsLoading(false);
    }
  };

  if (status.data && !status.data.mail_enabled) {
    return (
      <AuthShell>
        <p style={{ margin: 0, textAlign: 'center', lineHeight: 1.5, color: 'var(--app-text-primary)' }}>
          Восстановление по почте пока не работает. Напишите администратору Petzy, он задаст новый пароль.
        </p>
        <p style={{ margin: 'var(--spacing-lg) 0 0', textAlign: 'center' }}>
          <Link to="/login" style={linkStyle}>Вернуться ко входу</Link>
        </p>
      </AuthShell>
    );
  }

  if (sent) {
    return (
      <AuthShell>
        <h2 style={{ margin: '0 0 var(--spacing-md)', fontSize: 'var(--text-lg)', textAlign: 'center' }}>Проверьте почту</h2>
        <p style={{ margin: 0, textAlign: 'center', lineHeight: 1.5, color: 'var(--app-text-primary)' }}>{sent}.</p>
        <p style={{ margin: 'var(--spacing-md) 0 0', textAlign: 'center', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
          Ссылка работает один час. Письма нет? Загляните в «Спам». Если почту к аккаунту не привязывали, напишите администратору Petzy.
        </p>
        <p style={{ margin: 'var(--spacing-lg) 0 0', textAlign: 'center' }}>
          <Link to="/login" style={linkStyle}>Вернуться ко входу</Link>
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <h2 style={{ margin: '0 0 var(--spacing-sm)', fontSize: 'var(--text-lg)', textAlign: 'center' }}>Новый пароль</h2>
      <p style={{ margin: '0 0 var(--spacing-md)', textAlign: 'center', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
        Пришлём ссылку на почту, которую вы подтвердили в аккаунте
      </p>
      <Form
        layout="vertical"
        onFinish={submit}
        footer={
          <>
            <Button block color="primary" size="large" type="submit" loading={isLoading} disabled={isLoading}
              style={{ background: 'var(--app-cta-gradient)', border: 'none' }}>
              Отправить ссылку
            </Button>
            <p style={{ margin: 'var(--spacing-md) 0 0', textAlign: 'center', fontSize: 'var(--text-sm)' }}>
              <Link to="/login" style={linkStyle}>Вернуться ко входу</Link>
            </p>
          </>
        }
      >
        <Form.Item label={<span style={{ fontWeight: 500 }}>Логин или почта</span>}>
          <Input value={login} onChange={setLogin} placeholder="vera или vera@example.com" clearable autoComplete="username" disabled={isLoading} />
        </Form.Item>
      </Form>
    </AuthShell>
  );
}

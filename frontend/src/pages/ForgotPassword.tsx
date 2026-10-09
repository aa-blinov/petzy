import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button, Form, Input } from 'antd-mobile';
import { authService } from '../services/auth.service';
import type { ForgotPasswordResult } from '../services/auth.service';
import { AuthShell } from '../components/AuthShell';
import { FieldError } from '../components/FieldError';
import { useTouched } from '../hooks/useTouched';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { retryNote, useRetryLock } from '../utils/authForms';

const linkStyle = { color: 'var(--app-accent-deep)', fontWeight: 500 } as const;

/** «Забыли пароль?»: a link to set a new one, sent to the confirmed email. */
export function ForgotPassword() {
  const [login, setLogin] = useState('');
  const [sent, setSent] = useState<ForgotPasswordResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const { touch, shows } = useTouched(submitted);
  const status = useQuery({ queryKey: ['registration-status'], queryFn: () => authService.registrationStatus() });
  // A 429 says the address has five requests an hour: the form counts the
  // wait down instead of letting the next one be refused unseen.
  const { left: retryLeft, lock: lockAfterRefusal } = useRetryLock();
  const locked = retryLeft > 0;
  // Recovery needs mail: without it the request would go nowhere, so the
  // form waits for that word instead of being sent blind.
  const mailOff = !!status.data && !status.data.mail_enabled;
  const canAsk = status.isSuccess && !mailOff && !locked;

  // Said under the field, like on the reset screen, so it survives the next
  // render instead of living in a toast that is gone in a moment.
  const loginError = login.trim() ? null : 'Введите логин или почту';

  const submit = async () => {
    setSubmitted(true);
    if (loginError) return;
    setIsLoading(true);
    try {
      setSent(await authService.forgotPassword(login.trim()));
    } catch (err) {
      lockAfterRefusal(err);
      showToast.failure(getApiErrorMessage(err, 'Не удалось отправить запрос. Проверьте соединение'));
    } finally {
      setIsLoading(false);
    }
  };

  if (mailOff) {
    return (
      <AuthShell title="Новый пароль">
        <p style={{ margin: 0, textAlign: 'center', lineHeight: 1.5, color: 'var(--app-text-primary)' }}>
          Восстановление по почте пока не работает. Напишите администратору Petzy, он задаст новый пароль
        </p>
        <p style={{ margin: 'var(--spacing-lg) 0 0', textAlign: 'center' }}>
          <Link to="/login" className="tap-link" style={linkStyle}>Вернуться ко входу</Link>
        </p>
      </AuthShell>
    );
  }

  if (sent) {
    return (
      <AuthShell title="Проверьте почту">
        {/* The server says whether a letter is already on its way: the screen
            used to say «sent» every time, and the person waited for a second
            letter that was never going to come. */}
        <p style={{ margin: 0, textAlign: 'center', lineHeight: 1.5, color: 'var(--app-text-primary)' }}>
          {sent.already_sent ? 'Письмо уже отправляли недавно, ещё одно придёт позже' : sent.message}
        </p>
        <p style={{ margin: 'var(--spacing-md) 0 0', textAlign: 'center', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
          Ссылка работает один час. Письма нет? Загляните в «Спам». Если почту к аккаунту не привязывали, напишите администратору Petzy
        </p>
        <div style={{ marginTop: 'var(--spacing-lg)' }}>
          <Button
            block
            size="large"
            fill="outline"
            color="primary"
            disabled={isLoading || !canAsk}
            loading={isLoading}
            onClick={submit}
          >
            Отправить ещё раз
          </Button>
          {locked && (
            <p role="status" style={{ margin: 'var(--spacing-sm) 0 0', fontSize: 'var(--text-xs)', lineHeight: 1.4, textAlign: 'center', color: 'var(--app-text-secondary)' }}>
              {retryNote(retryLeft)}
            </p>
          )}
        </div>
        <p style={{ margin: 'var(--spacing-md) 0 0', textAlign: 'center' }}>
          <Link to="/login" className="tap-link" style={linkStyle}>Вернуться ко входу</Link>
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Новый пароль">
      <p style={{ margin: '0 0 var(--spacing-md)', textAlign: 'center', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
        Пришлём ссылку на почту, которую вы подтвердили в аккаунте
      </p>
      <Form
        layout="vertical"
        onFinish={submit}
        footer={
          <>
            <Button block color="primary" size="large" type="submit" data-enter-submit loading={isLoading} disabled={isLoading || !canAsk}
              style={{ background: 'var(--app-cta-gradient)', border: 'none' }}>
              Отправить ссылку
            </Button>
            {!status.isSuccess && !status.isError && (
              <p role="status" style={{ margin: 'var(--spacing-sm) 0 0', fontSize: 'var(--text-xs)', lineHeight: 1.4, textAlign: 'center', color: 'var(--app-text-secondary)' }}>
                Проверяем, работает ли восстановление по почте
              </p>
            )}
            {(locked || status.isError) && (
              <p role="status" style={{ margin: 'var(--spacing-sm) 0 0', fontSize: 'var(--text-xs)', lineHeight: 1.4, textAlign: 'center', color: 'var(--app-text-secondary)' }}>
                {locked
                  ? retryNote(retryLeft)
                  : 'Не удалось узнать, работает ли восстановление по почте. Проверьте соединение и попробуйте ещё раз'}
              </p>
            )}
            <p style={{ margin: 'var(--spacing-md) 0 0', textAlign: 'center', fontSize: 'var(--text-sm)' }}>
              <Link to="/login" className="tap-link" style={linkStyle}>Вернуться ко входу</Link>
            </p>
            {/* Someone who never had an account can arrive here from the sign-in
                screen; the way to one is a word, not a hunt. Only while the
                server says the sign-up is open. */}
            {status.data?.open !== false && (
              <p style={{ margin: 'var(--spacing-sm) 0 0', textAlign: 'center', fontSize: 'var(--text-sm)' }}>
                <Link to="/register" className="tap-link" style={linkStyle}>Создать аккаунт</Link>
              </p>
            )}
          </>
        }
      >
        <Form.Item
          label={<span style={{ fontWeight: 500 }}>Логин или почта</span>}
          description={shows('login') && loginError
            ? <FieldError message={loginError} />
            : <span style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)' }}>Письмо придёт на подтверждённый адрес аккаунта</span>}
        >
          <Input value={login} onChange={setLogin} onBlur={touch('login')} placeholder="vera или vera@example.com" clearable autoComplete="username" disabled={isLoading} />
        </Form.Item>
      </Form>
    </AuthShell>
  );
}

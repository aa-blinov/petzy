import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button, Form, Input } from 'antd-mobile';
import { isAxiosError } from 'axios';
import { authService } from '../services/auth.service';
import { useAuth } from '../hooks/useAuth';
import { AuthShell } from '../components/AuthShell';
import { FieldError } from '../components/FieldError';
import { useTouched } from '../hooks/useTouched';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { passwordProblem } from '../utils/authForms';

const linkStyle = { color: 'var(--app-accent-deep)', fontWeight: 600 } as const;

/** The link from «Petzy: новый пароль»: set a new password and go in. */
export function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const navigate = useNavigate();
  const { signedIn } = useAuth();
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const { touch, shows } = useTouched(submitted);
  const [isLoading, setIsLoading] = useState(false);
  const [linkDead, setLinkDead] = useState(!token);

  const passwordError = passwordProblem(password);
  const repeatError = repeat !== password ? 'Пароли не совпадают' : null;

  const submit = async () => {
    setSubmitted(true);
    if (passwordError || repeatError) return;
    setIsLoading(true);
    try {
      const username = await authService.resetPassword(token, password);
      await signedIn(username);
      showToast.success('Пароль изменён');
      navigate('/', { replace: true });
    } catch (err) {
      if (isAxiosError<{ code?: string }>(err) && err.response?.data?.code === 'account_link_invalid') {
        setLinkDead(true);
      } else {
        showToast.failure(getApiErrorMessage(err, 'Не удалось сменить пароль. Проверьте соединение'));
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (linkDead) {
    return (
      <AuthShell title="Новый пароль">
        <p style={{ margin: 0, textAlign: 'center', lineHeight: 1.5, color: 'var(--app-text-primary)' }}>
          Ссылка устарела или уже использована. Запросите новую, она придёт на ту же почту
        </p>
        <p style={{ margin: 'var(--spacing-lg) 0 0', textAlign: 'center' }}>
          <Link to="/forgot-password" className="tap-link" style={linkStyle}>Запросить новую ссылку</Link>
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Новый пароль">
      <p style={{ margin: '0 0 var(--spacing-md)', textAlign: 'center', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
        После смены пароля на других устройствах придётся войти заново
      </p>
      <Form
        layout="vertical"
        onFinish={submit}
        footer={
          <>
            <Button block color="primary" size="large" type="submit" data-enter-submit loading={isLoading} disabled={isLoading}
              style={{ background: 'var(--app-cta-gradient)', border: 'none' }}>
              Сохранить и войти
            </Button>
            <p style={{ margin: 'var(--spacing-md) 0 0', textAlign: 'center', fontSize: 'var(--text-sm)' }}>
              <Link to="/login" className="tap-link" style={linkStyle}>Вернуться ко входу</Link>
            </p>
          </>
        }
      >
        <Form.Item
          label={<span style={{ fontWeight: 500 }}>Новый пароль</span>}
          description={shows('password') && passwordError
            ? <FieldError message={passwordError} />
            : <span style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)' }}>Не короче 8 символов, не длиннее 72 байт, хотя бы три разных символа</span>}
        >
          <Input type="password" value={password} onChange={setPassword} onBlur={touch('password')} placeholder="Новый пароль" clearable autoComplete="new-password" disabled={isLoading} />
        </Form.Item>
        <Form.Item
          label={<span style={{ fontWeight: 500 }}>Ещё раз</span>}
          description={shows('repeat') && repeatError ? <FieldError message={repeatError} /> : undefined}
        >
          <Input type="password" value={repeat} onChange={setRepeat} onBlur={touch('repeat')} placeholder="Повторите пароль" clearable autoComplete="new-password" disabled={isLoading} />
        </Form.Item>
      </Form>
    </AuthShell>
  );
}

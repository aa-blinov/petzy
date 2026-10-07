import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
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

/** What the server takes (web/schemas.py PasswordResetRequest) and what its
 *  password rule allows (72 bytes, web/auth.py password_problem). Typing past
 *  it used to be silently accepted and then refused after the round trip. */
const PASSWORD_MAX = 72;

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
  const [linkSpent, setLinkSpent] = useState(!token);
  // Asked once when the screen opens, so a link that expired or was already
  // used is said at once instead of after a password has been picked. The
  // check only reads the link, so a working one goes on to the form.
  const linkCheck = useQuery({
    queryKey: ['reset-link', token],
    queryFn: () => authService.checkResetLink(token),
    enabled: !!token,
    staleTime: Infinity,
    retry: false,
  });
  const linkDead = linkSpent || linkCheck.data === false;

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
        setLinkSpent(true);
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
        {/* role="status": the screen changes without a page load, and a screen
            reader is otherwise left with the word it was on. */}
        <p role="status" style={{ margin: 0, textAlign: 'center', lineHeight: 1.5, color: 'var(--app-text-primary)' }}>
          Ссылка не сработала: она устарела или уже использована
        </p>
        <p style={{ margin: 'var(--spacing-md) 0 0', textAlign: 'center', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
          Пришлём новую на ту же почту, что и в прошлый раз
        </p>
        <p style={{ margin: 'var(--spacing-lg) 0 0', textAlign: 'center' }}>
          <Link to="/forgot-password" className="tap-link" style={linkStyle}>Отправить новое письмо</Link>
        </p>
      </AuthShell>
    );
  }

  // While the check is in flight the form is not shown yet: it would only
  // disappear a moment later if the link has expired. A failed check leaves
  // the form alone, so a bad connection doesn't lock anyone out of resetting.
  if (token && linkCheck.isPending) {
    return (
      <AuthShell title="Новый пароль">
        <p role="status" style={{ margin: 0, textAlign: 'center', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
          Проверяем ссылку
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
            : <span style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)' }}>Не короче 8 символов, хотя бы три разных</span>}
        >
          <Input type="password" value={password} onChange={setPassword} onBlur={touch('password')} placeholder="Новый пароль" clearable autoComplete="new-password" disabled={isLoading} maxLength={PASSWORD_MAX} />
        </Form.Item>
        <Form.Item
          label={<span style={{ fontWeight: 500 }}>Ещё раз</span>}
          description={shows('repeat') && repeatError ? <FieldError message={repeatError} /> : undefined}
        >
          <Input type="password" value={repeat} onChange={setRepeat} onBlur={touch('repeat')} placeholder="Повторите пароль" clearable autoComplete="new-password" disabled={isLoading} maxLength={PASSWORD_MAX} />
        </Form.Item>
      </Form>
    </AuthShell>
  );
}

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Button, SpinLoading } from 'antd-mobile';
import { isAxiosError } from 'axios';
import { authService } from '../services/auth.service';
import { AuthShell } from '../components/AuthShell';

type State = 'checking' | 'done' | 'dead' | 'taken' | 'failed';

/** The link from «Petzy: подтвердите почту». Works without being signed
 *  in: the letter may be opened on another device. */
export function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [state, setState] = useState<State>(token ? 'checking' : 'dead');
  const once = useRef(false);

  // What the link says once the server has looked at it.
const ask = useCallback(
    () =>
      authService.verifyEmail(token).then(
        () => 'done' as State,
        (err) => {
          const code = isAxiosError<{ code?: string }>(err) ? err.response?.data?.code : undefined;
          return code === 'account_link_invalid' ? 'dead' : code === 'account_email_taken' ? 'taken' : 'failed';
        },
      ),
    [token],
  );

  useEffect(() => {
    // Once on its own: the token is spent on the first try (StrictMode runs effects twice).
    if (!token || once.current) return;
    once.current = true;
    void ask().then(setState);
  }, [ask, token]);

  const retry = () => {
    once.current = true;
    setState('checking');
    void ask().then(setState);
  };

  const text: Record<State, string> = {
    checking: 'Подтверждаем почту…',
    done: 'Почта подтверждена. Если забудете пароль, ссылка для нового придёт на неё',
    dead: 'Ссылка устарела или уже использована. Отправить новое письмо можно в Настройках, в разделе «Почта»',
    taken: 'Эта почта уже подтверждена в другом аккаунте Petzy. Укажите другую в Настройках',
    failed: 'Не удалось подтвердить почту. Проверьте соединение и попробуйте ещё раз',
  };

  // The words name the way out, so each state offers it: the letter is often opened on a device
  // that has no session, and a single link to `/` lands such a person on the sign-in screen
  // instead of the settings section the sentence told them about.
  const links: Record<State, { to: string; label: string }[]> = {
    checking: [],
    done: [{ to: '/', label: 'Открыть Petzy' }],
    dead: [
      { to: '/', label: 'Открыть Petzy' },
      { to: '/settings/email', label: 'Настройки, Почта' },
      { to: '/login', label: 'Войти' },
    ],
    taken: [
      { to: '/', label: 'Открыть Petzy' },
      { to: '/settings/email', label: 'Настройки, Почта' },
      { to: '/login', label: 'Войти' },
    ],
    failed: [{ to: '/', label: 'Открыть Petzy' }],
  };

  const linkStyle = { color: 'var(--app-accent-deep)', fontWeight: 600 };

  return (
    <AuthShell>
      <div style={{ textAlign: 'center' }}>
        {state === 'checking' && <SpinLoading style={{ margin: '0 auto var(--spacing-md)' }} />}
        <p style={{ margin: 0, lineHeight: 1.5, color: 'var(--app-text-primary)' }} role="status">
          {text[state]}
        </p>
        {state === 'failed' && (
          <Button block color="primary" fill="outline" style={{ marginTop: 'var(--spacing-lg)' }} onClick={retry}>
            Повторить
          </Button>
        )}
        {state !== 'checking' && links[state].length > 0 && (
          <div style={{ margin: 'var(--spacing-lg) 0 0', display: 'grid', gap: 'var(--spacing-sm)' }}>
            {links[state].map(({ to, label }) => (
              <Link key={to} to={to} className="tap-link" style={linkStyle}>
                {label}
              </Link>
            ))}
          </div>
        )}
      </div>
    </AuthShell>
  );
}
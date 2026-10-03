import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { SpinLoading } from 'antd-mobile';
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

  useEffect(() => {
    // Once: the token is spent on the first try (StrictMode runs effects twice).
    if (!token || once.current) return;
    once.current = true;
    authService
      .verifyEmail(token)
      .then(() => setState('done'))
      .catch((err) => {
        const code = isAxiosError<{ code?: string }>(err) ? err.response?.data?.code : undefined;
        setState(code === 'account_link_invalid' ? 'dead' : code === 'account_email_taken' ? 'taken' : 'failed');
      });
  }, [token]);

  const text: Record<State, string> = {
    checking: 'Подтверждаем почту…',
    done: 'Почта подтверждена. Если забудете пароль, ссылка для нового придёт на неё',
    dead: 'Ссылка устарела или уже использована. Отправить новое письмо можно в Настройках, в разделе «Почта»',
    taken: 'Эта почта уже подтверждена в другом аккаунте Petzy. Укажите другую в Настройках',
    failed: 'Не удалось подтвердить почту. Проверьте соединение и откройте ссылку ещё раз',
  };

  return (
    <AuthShell>
      <div style={{ textAlign: 'center' }}>
        {state === 'checking' && <SpinLoading style={{ margin: '0 auto var(--spacing-md)' }} />}
        <p style={{ margin: 0, lineHeight: 1.5, color: 'var(--app-text-primary)' }} role="status">
          {text[state]}
        </p>
        {state !== 'checking' && (
          <p style={{ margin: 'var(--spacing-lg) 0 0' }}>
            <Link to="/" style={{ color: 'var(--app-accent-deep)', fontWeight: 600 }}>Открыть Petzy</Link>
          </p>
        )}
      </div>
    </AuthShell>
  );
}

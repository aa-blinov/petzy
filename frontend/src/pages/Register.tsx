import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button, Checkbox, Form, Input } from 'antd-mobile';
import { useAuth } from '../hooks/useAuth';
import { authService } from '../services/auth.service';
import { AuthShell } from '../components/AuthShell';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { FieldError } from '../components/FieldError';

/** The server's own rule (web/auth.py USERNAME_RE), checked here first so
 *  the mistake shows under the field rather than after a round trip. */
const USERNAME_RE = /^[a-z0-9][a-z0-9._-]{2,29}$/;

const labelStyle = { color: 'var(--app-text-primary)', fontWeight: 500 } as const;
const legalLinkStyle = { color: 'var(--app-accent-deep)', fontWeight: 500 } as const;
const hintStyle = { fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)', lineHeight: 1.4 } as const;

export function Register() {
  const { register, username: storedUsername } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [consent, setConsent] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const status = useQuery({ queryKey: ['registration-status'], queryFn: () => authService.registrationStatus() });

  // Already signed in on this device (see Login for the same check).
  if (storedUsername) return <Navigate to="/" replace />;

  const usernameError =
    username.length === 0
      ? 'Придумайте логин'
      : !USERNAME_RE.test(username)
        ? 'От 3 до 30 символов: латинские буквы, цифры, точка, дефис или подчёркивание, начиная с буквы или цифры'
        : null;
  const nameError = fullName.trim() ? null : 'Напишите имя';
  // Asked only while mail works: without it there's nothing to recover with.
  const askEmail = !!status.data?.mail_enabled;
  const emailError = !askEmail
    ? null
    : !email.trim()
      ? 'Укажите почту'
      : !/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email.trim())
        ? 'Проверьте адрес почты'
        : null;
  const passwordError = password.length < 8 ? 'Не короче 8 символов' : null;
  const repeatError = repeat !== password ? 'Пароли не совпадают' : null;
  const consentError = consent ? null : 'Без согласия аккаунт не создать';

  const handleSubmit = async () => {
    setSubmitted(true);
    if (usernameError || nameError || emailError || passwordError || repeatError || consentError) return;
    setIsLoading(true);
    try {
      await register({
        username,
        password,
        full_name: fullName.trim(),
        email: askEmail ? email.trim() : undefined,
        privacy_consent: consent,
      });
      // A new account has no pets yet: the feed sends it to an invitation
      // waiting for it, or to onboarding.
      navigate('/', { replace: true });
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось создать аккаунт. Проверьте соединение'));
    } finally {
      setIsLoading(false);
    }
  };

  if (status.data?.open === false) {
    return (
      <AuthShell>
        <p style={{ margin: 0, textAlign: 'center', color: 'var(--app-text-primary)', lineHeight: 1.5 }}>
          Регистрация сейчас закрыта. Попросите администратора Petzy создать вам аккаунт.
        </p>
        <div style={{ textAlign: 'center', marginTop: 'var(--spacing-lg)' }}>
          <Link to="/login" className="tap-link" style={{ color: 'var(--app-accent-deep)', fontWeight: 600 }}>
            Войти
          </Link>
        </div>
      </AuthShell>
    );
  }

  /** Under the field: the rule's error once a submit was tried, else the hint. */
  const below = (error: string | null, hint?: string) =>
    submitted && error ? <FieldError message={error} /> : hint ? <span style={hintStyle}>{hint}</span> : undefined;

  return (
    <AuthShell>
      <h2 style={{ margin: '0 0 var(--spacing-md)', fontSize: 'var(--text-lg)', textAlign: 'center', color: 'var(--app-text-primary)' }}>
        Новый аккаунт
      </h2>
      <Form
        layout="vertical"
        onFinish={handleSubmit}
        footer={
          <>
            <Button
              color="primary"
              block
              size="large"
              loading={isLoading}
              disabled={isLoading}
              type="submit"
              style={{ marginTop: 8, background: 'var(--app-cta-gradient)', border: 'none' }}
            >
              Создать аккаунт
            </Button>
            <p style={{ margin: 'var(--spacing-md) 0 0', fontSize: 'var(--text-sm)', textAlign: 'center', color: 'var(--app-text-secondary)' }}>
              Уже есть аккаунт?{' '}
              <Link to="/login" className="tap-link" style={{ color: 'var(--app-accent-deep)', fontWeight: 600 }}>
                Войти
              </Link>
            </p>
          </>
        }
      >
        <Form.Item
          label={<span style={labelStyle}>Логин</span>}
          description={below(usernameError, 'По нему вас найдут для общего доступа')}
        >
          <Input
            placeholder="например, vera"
            value={username}
            // Logins are lowercase: typed capitals simply become small letters.
            onChange={(val) => setUsername(val.trim().toLowerCase())}
            disabled={isLoading}
            clearable
            autoComplete="username"
          />
        </Form.Item>
        <Form.Item
          label={<span style={labelStyle}>Как к вам обращаться</span>}
          description={below(nameError, 'Видят те, с кем вы делитесь питомцем')}
        >
          <Input
            placeholder="Имя"
            value={fullName}
            onChange={setFullName}
            disabled={isLoading}
            clearable
            autoComplete="name"
          />
        </Form.Item>
        {askEmail && (
          <Form.Item
            label={<span style={labelStyle}>Почта</span>}
            description={below(emailError, 'Чтобы восстановить пароль')}
          >
            <Input
              type="email"
              placeholder="name@example.com"
              value={email}
              onChange={setEmail}
              disabled={isLoading}
              clearable
              autoComplete="email"
            />
          </Form.Item>
        )}
        <Form.Item label={<span style={labelStyle}>Пароль</span>} description={below(passwordError, 'Не короче 8 символов')}>
          <Input
            type="password"
            placeholder="Придумайте пароль"
            value={password}
            onChange={setPassword}
            disabled={isLoading}
            clearable
            autoComplete="new-password"
          />
        </Form.Item>
        <Form.Item label={<span style={labelStyle}>Пароль ещё раз</span>} description={below(repeatError)}>
          <Input
            type="password"
            placeholder="Повторите пароль"
            value={repeat}
            onChange={setRepeat}
            disabled={isLoading}
            clearable
            autoComplete="new-password"
          />
        </Form.Item>
        <Form.Item description={below(consentError)}>
          {/* The texts open in a new tab: following them here would lose the form. */}
          <Checkbox
            checked={consent}
            onChange={setConsent}
            disabled={isLoading}
            style={{ '--icon-size': '20px', '--gap': '10px', '--font-size': 'var(--text-sm)', alignItems: 'flex-start', lineHeight: 1.45 }}
          >
            <span style={{ color: 'var(--app-text-primary)' }}>
              Даю{' '}
              <a href="/consent" target="_blank" rel="noopener" onClick={e => e.stopPropagation()} style={legalLinkStyle}>
                согласие на обработку персональных данных
              </a>{' '}
              на условиях{' '}
              <a href="/privacy" target="_blank" rel="noopener" onClick={e => e.stopPropagation()} style={legalLinkStyle}>
                политики конфиденциальности
              </a>
            </span>
          </Checkbox>
        </Form.Item>
      </Form>
    </AuthShell>
  );
}

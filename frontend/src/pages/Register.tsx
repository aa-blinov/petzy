import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button, Checkbox, Form, Input } from 'antd-mobile';
import { useAuth } from '../hooks/useAuth';
import { authService } from '../services/auth.service';
import { AuthShell } from '../components/AuthShell';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { FieldError } from '../components/FieldError';
import { useTouched } from '../hooks/useTouched';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { passwordProblem } from '../utils/authForms';

/** The server's own rule (web/auth.py USERNAME_RE), checked here first so
 *  the mistake shows under the field rather than after a round trip. */
const USERNAME_RE = /^[a-z0-9][a-z0-9._-]{2,29}$/;

/** What the field says when the server keeps the password in its list of the
 *  most guessed ones. The list never comes to the screen, only this. */
const COMMON_PASSWORD_NOTE = 'Это один из самых частых паролей, придумайте другой';

/** How long the typing has to pause before the server is asked about the
 *  password: long enough not to go out on every letter, short enough to
 *  answer while the person is still at the field. */
const COMMON_CHECK_AFTER_MS = 600;

const labelStyle = { color: 'var(--app-text-primary)', fontWeight: 500 } as const;
const legalLinkStyle = { color: 'var(--app-accent-deep)', fontWeight: 500 } as const;
const hintStyle = { fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)', lineHeight: 1.4 } as const;

/** The last value of `value`, once it has stopped changing. */
function useSettled(value: string, delay: number): string {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return settled;
}

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
  const { touch, shows } = useTouched(submitted);
  const [isLoading, setIsLoading] = useState(false);
  // Five typed fields are five words of effort, and leaving the screen used
  // to throw them away without a word, unlike every other form here.
  const { dialog: leaveDialog, release: releaseLeave } = useUnsavedChangesGuard(
    !!username || !!fullName || !!email || !!password || !!repeat,
  );

  const status = useQuery({ queryKey: ['registration-status'], queryFn: () => authService.registrationStatus() });
  const passwordRuleError = passwordProblem(password, username);
  // The most guessed passwords are a list on the server, so the form asks
  // about this one password, after a pause in typing. A failed ask says
  // nothing: the rule that refuses it is still there on the server.
  const settledPassword = useSettled(password, COMMON_CHECK_AFTER_MS);
  const commonCheck = useQuery({
    queryKey: ['common-password', settledPassword],
    queryFn: () => authService.isCommonPassword(settledPassword),
    enabled: settledPassword === password && !!password && !passwordRuleError,
    staleTime: Infinity,
    retry: false,
  });
  const commonPassword = commonCheck.data === true;
  // Whether an address is asked for is the server's word, but it can't be
  // known for a moment: sending before it arrives meant a form with no mail
  // field answered 422. The field shows right away and goes only if the
  // server says letters are off; until the answer comes the form waits.
  const statusKnown = status.isSuccess;
  const askEmail = status.data?.mail_enabled !== false;

  // Already signed in on this device (see Login for the same check).
  if (storedUsername) return <Navigate to="/" replace />;

  const usernameError =
    username.length === 0
      ? 'Придумайте логин'
      : !USERNAME_RE.test(username)
        ? 'От 3 до 30 символов: латинские буквы, цифры, точка, дефис или подчёркивание, начиная с буквы или цифры'
        : null;
  const nameError = fullName.trim() ? null : 'Напишите имя';
  const emailError = !askEmail
    ? null
    : !email.trim()
      ? 'Укажите почту'
      : !/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email.trim())
        ? 'Проверьте адрес почты'
        : null;
  const passwordError = commonPassword ? COMMON_PASSWORD_NOTE : passwordRuleError;
  const repeatError = repeat !== password ? 'Пароли не совпадают' : null;
  const consentError = consent ? null : 'Без согласия аккаунт не создать';

  const handleSubmit = async () => {
    setSubmitted(true);
    if (usernameError || nameError || emailError || passwordError || repeatError || consentError) return;
    if (!statusKnown) return;
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
      // waiting for it, or to onboarding. The account exists now, so the
      // way out no longer asks.
      releaseLeave();
      navigate('/', { replace: true });
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось создать аккаунт. Проверьте соединение'));
    } finally {
      setIsLoading(false);
    }
  };

  if (status.data?.open === false) {
    return (
      <AuthShell title="Новый аккаунт">
        <p style={{ margin: 0, textAlign: 'center', color: 'var(--app-text-primary)', lineHeight: 1.5 }}>
          Регистрация сейчас закрыта. Попросите администратора Petzy создать вам аккаунт
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
  const below = (name: string, error: string | null, hint?: string) =>
    shows(name) && error ? <FieldError message={error} /> : hint ? <span style={hintStyle}>{hint}</span> : undefined;

  return (
    <AuthShell title="Новый аккаунт">
      {!statusKnown && !status.isError && (
        <p style={{ margin: '0 0 var(--spacing-md)', fontSize: 'var(--text-sm)', lineHeight: 1.5, textAlign: 'center', color: 'var(--app-text-secondary)' }}>
          Проверяем, можно ли сейчас создать аккаунт
        </p>
      )}
      {status.isError && (
        <p style={{ margin: '0 0 var(--spacing-md)', fontSize: 'var(--text-sm)', lineHeight: 1.5, textAlign: 'center', color: 'var(--app-text-secondary)' }}>
          Не удалось узнать, можно ли создать аккаунт. Проверьте соединение и попробуйте ещё раз
        </p>
      )}
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
              disabled={isLoading || !statusKnown || status.isError}
              type="submit"
              data-enter-submit
              style={{ marginTop: 8, background: 'var(--app-cta-gradient)', border: 'none' }}
            >
              Создать аккаунт
            </Button>
            {status.isError && (
              <Button
                block
                size="large"
                fill="outline"
                color="primary"
                type="button"
                disabled={isLoading}
                onClick={() => {
                  void status.refetch();
                }}
                style={{ marginTop: 'var(--spacing-md)' }}
              >
                Повторить
              </Button>
            )}
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
          description={below('username', usernameError, 'По нему вас найдут для общего доступа')}
        >
          <Input
            placeholder="например, vera"
            onBlur={touch('username')}
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
          description={below('name', nameError, 'Видят те, с кем вы делитесь питомцем')}
        >
          <Input
            placeholder="Имя"
            onBlur={touch('name')}
            maxLength={100}
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
            description={below('email', emailError, 'Чтобы восстановить пароль')}
          >
            <Input
              type="email"
              placeholder="name@example.com"
              onBlur={touch('email')}
              maxLength={254}
              value={email}
              onChange={setEmail}
              disabled={isLoading}
              clearable
              autoComplete="email"
            />
          </Form.Item>
        )}
        <Form.Item
          label={<span style={labelStyle}>Пароль</span>}
          // The server's answer about a guessed password shows right away:
          // it isn't a guess, the list is the server's.
          description={commonPassword
            ? <FieldError message={COMMON_PASSWORD_NOTE} />
            : below('password', passwordError, 'Не короче 8 символов, хотя бы три разных')}
        >
          <Input
            type="password"
            placeholder="Придумайте пароль"
            onBlur={touch('password')}
            value={password}
            onChange={setPassword}
            disabled={isLoading}
            clearable
            autoComplete="new-password"
          />
        </Form.Item>
        <Form.Item label={<span style={labelStyle}>Пароль ещё раз</span>} description={below('repeat', repeatError)}>
          <Input
            type="password"
            placeholder="Повторите пароль"
            onBlur={touch('repeat')}
            value={repeat}
            onChange={setRepeat}
            disabled={isLoading}
            clearable
            autoComplete="new-password"
          />
        </Form.Item>
        <Form.Item
          description={(submitted && consentError ? <FieldError message={consentError} /> : undefined)}
        >
          {/* The texts open in a new tab: following them here would lose the form.
              Said out loud as well as shown, so a screen reader hears where the
              link goes before it is followed. */}
          <Checkbox
            checked={consent}
            onChange={setConsent}
            disabled={isLoading}
            style={{ '--icon-size': '20px', '--gap': '10px', '--font-size': 'var(--text-sm)', alignItems: 'flex-start', lineHeight: 1.45 }}
          >
            <span style={{ color: 'var(--app-text-primary)' }}>
              Даю{' '}
              <a
                href="/consent"
                target="_blank"
                rel="noopener"
                onClick={e => e.stopPropagation()}
                style={legalLinkStyle}
                aria-label="согласие на обработку персональных данных, откроется в новой вкладке"
              >
                согласие на обработку персональных данных
              </a>{' '}
              на условиях{' '}
              <a
                href="/privacy"
                target="_blank"
                rel="noopener"
                onClick={e => e.stopPropagation()}
                style={legalLinkStyle}
                aria-label="политики конфиденциальности, откроется в новой вкладке"
              >
                политики конфиденциальности
              </a>
              <span style={{ display: 'block', color: 'var(--app-text-secondary)', fontSize: 'var(--text-xs)', marginTop: 2 }}>
                Тексты откроются в новой вкладке
              </span>
            </span>
          </Checkbox>
        </Form.Item>
      </Form>
      {leaveDialog}
    </AuthShell>
  );
}

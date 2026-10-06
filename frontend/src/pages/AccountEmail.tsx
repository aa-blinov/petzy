import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Dialog, Form, Input } from 'antd-mobile';
import { isAxiosError } from 'axios';
import { FieldError } from '../components/FieldError';
import { fieldNote } from '../components/FieldNote';
import { accountService, ACCOUNT_QUERY_KEY } from '../services/account.service';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { goBack } from '../utils/navigation';
import { onInvalidSubmit } from '../utils/formErrors';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';

const noteStyle = { margin: '0 var(--spacing-md) var(--spacing-md)', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' } as const;

/** Настройки → «Почта»: the address password reset links go to. */
export function AccountEmail() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: account, isLoading, isError, refetch } = useQuery({ queryKey: ACCOUNT_QUERY_KEY, queryFn: () => accountService.get() });
  const [email, setEmail] = useState<string | null>(null);
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState<'save' | 'resend' | 'remove' | null>(null);
  const [asked, setAsked] = useState(false);
  // What the server refused: said under the field that caused it, the toast
  // stays as its echo. A toast alone is gone by the time the eye goes back
  // to the form, and the field itself was left unmarked.
  const [saveError, setSaveError] = useState<{ field: 'email' | 'password'; text: string } | null>(null);

  const current = account?.email || account?.pending_email || '';
  // An emptied field means «leave the address as it is», not «remove it»:
  // removal is the separate button below. So the current address comes back
  // into the field rather than the field quietly losing it.
  const value = email === '' ? current : (email ?? current);
  const saveEmailError = saveError?.field === 'email' ? saveError.text : null;
  const savePasswordError = saveError?.field === 'password' ? saveError.text : null;
  // What was typed and not saved: the question before leaving, like every other form.
  const dirty = !!password || (email !== null && email !== '' && email.trim() !== current);
  const { dialog: leaveDialog } = useUnsavedChangesGuard(dirty);

  const save = async (next: string, kind: 'save' | 'remove') => {
    setAsked(true);
    setSaveError(null);
    if (!password) {
      onInvalidSubmit({ password: { type: 'required', message: 'Введите текущий пароль' } });
      return;
    }
    if (kind === 'remove') {
      const sure = await Dialog.confirm({
        content: 'Удалить почту? Без неё забытый пароль придётся сбрасывать через администратора',
        confirmText: 'Удалить',
        cancelText: 'Оставить',
      });
      if (!sure) return;
    }
    setBusy(kind);
    try {
      const updated = await accountService.changeEmail(next, password);
      queryClient.setQueryData(ACCOUNT_QUERY_KEY, updated);
      setPassword('');
      setAsked(false);
      setEmail(null);
      showToast.success(
        !next ? 'Почта удалена' : updated.pending_email ? `Письмо отправлено на ${updated.pending_email}` : 'Почта не изменилась',
      );
    } catch (err) {
      // A refused current password is that field's mistake; anything else is
      // about the address itself.
      const refusedPassword = isAxiosError<{ code?: string }>(err) && err.response?.data?.code === 'account_wrong_password';
      setSaveError({
        field: refusedPassword ? 'password' : 'email',
        text: getApiErrorMessage(err, 'Не удалось сохранить почту'),
      });
      showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить почту'));
    } finally {
      setBusy(null);
    }
  };

  const resend = async () => {
    setBusy('resend');
    try {
      await accountService.resendVerification();
      showToast.success('Письмо отправлено ещё раз');
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось отправить письмо'));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Почта</h1>
        </div>

        {/* Three states, not one: while the state of the address is still
            coming, saying «Отправка писем пока не настроена» was a claim
            nobody had made yet. */}
        {isLoading && (
          <p role="status" style={noteStyle}>Смотрим, какая почта указана</p>
        )}

        {isError && (
          <p style={noteStyle}>Не удалось узнать, какая почта указана. Проверьте соединение</p>
        )}
        {isError && (
          <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-md)' }}>
            <Button fill="outline" color="primary" block onClick={() => {
              void refetch();
            }}>
              Повторить
            </Button>
          </div>
        )}

        {account && !isError && !account.mail_enabled ? (
          <p style={noteStyle}>Отправка писем пока не настроена. Пока её нет, забытый пароль сбрасывает администратор Petzy</p>
        ) : (
          <>
            <p style={noteStyle}>
              {account?.email_verified && !account.pending_email
                ? `Подтверждена: ${account.email}. Если забудете пароль, ссылка для нового придёт сюда`
                : account?.pending_email
                  ? `${account.email_verified && account.email ? `Подтверждена: ${account.email} ` : ''}Ждёт подтверждения: ${account.pending_email}. Откройте ссылку из письма, оно действует сутки`
                  : 'Почта не указана. Без неё забытый пароль придётся сбрасывать через администратора'}
            </p>
            {account?.pending_email && (
              <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-md)' }}>
                <Button fill="outline" color="primary" block loading={busy === 'resend'} disabled={!!busy} onClick={resend}>
                  Отправить письмо ещё раз
                </Button>
              </div>
            )}
            <Form layout="vertical" mode="card">
              <Form.Item label="Адрес почты" description={fieldNote({ error: saveEmailError ?? undefined, value, max: 254 })}>
                <Input type="email" value={value} onChange={setEmail} placeholder="name@example.com" clearable maxLength={254} autoComplete="email" />
              </Form.Item>
              <Form.Item
                label="Текущий пароль"
                description={savePasswordError
                  ? <FieldError message={savePasswordError} />
                  : asked && !password
                    ? <FieldError message="Введите текущий пароль" />
                    : 'Почтой можно вернуть доступ к аккаунту, поэтому менять её можно только с паролем'}
              >
                <Input type="password" value={password} onChange={setPassword} placeholder="Пароль от Petzy" autoComplete="current-password" />
              </Form.Item>
            </Form>
            <div className="safe-area-padding form-actions">
              <Button block color="primary" size="large" data-enter-submit loading={busy === 'save'} disabled={!!busy || !value.trim()} onClick={() => save(value.trim(), 'save')}>
                Сохранить и подтвердить
              </Button>
              {/* Shown even when no address is set: the server takes the request
                  either way, and a button that comes and goes with the state
                  makes the screen ask itself whether there is anything to remove. */}
              <Button block fill="none" color="danger" loading={busy === 'remove'} disabled={!!busy} onClick={() => save('', 'remove')}>
                Удалить почту
              </Button>
              <Button block fill="none" onClick={() => goBack(navigate, '/settings')}>
                Назад
              </Button>
            </div>
          </>
        )}
      </div>
      {leaveDialog}
    </div>
  );
}

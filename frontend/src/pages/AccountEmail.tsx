import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Dialog, Form, Input } from 'antd-mobile';
import { FieldError } from '../components/FieldError';
import { accountService, ACCOUNT_QUERY_KEY } from '../services/account.service';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { goBack } from '../utils/navigation';

const noteStyle = { margin: '0 var(--spacing-md) var(--spacing-md)', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' } as const;

/** Настройки → «Почта»: the address password reset links go to. */
export function AccountEmail() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: account } = useQuery({ queryKey: ACCOUNT_QUERY_KEY, queryFn: () => accountService.get() });
  const [email, setEmail] = useState<string | null>(null);
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState<'save' | 'resend' | 'remove' | null>(null);
  const [asked, setAsked] = useState(false);

  const current = account?.email || account?.pending_email || '';
  const value = email ?? current;

  const save = async (next: string, kind: 'save' | 'remove') => {
    setAsked(true);
    if (!password) return;
    if (kind === 'remove') {
      const sure = await Dialog.confirm({
        content: 'Удалить почту? Без неё забытый пароль придётся сбрасывать через администратора.',
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

        {account && !account.mail_enabled ? (
          <p style={noteStyle}>Отправка писем пока не настроена. Пока её нет, забытый пароль сбрасывает администратор Petzy.</p>
        ) : (
          <>
            <p style={noteStyle}>
              {account?.email_verified && !account.pending_email
                ? `Подтверждена: ${account.email}. Если забудете пароль, ссылка для нового придёт сюда.`
                : account?.pending_email
                  ? `${account.email_verified && account.email ? `Подтверждена: ${account.email}. ` : ''}Ждёт подтверждения: ${account.pending_email}. Откройте ссылку из письма, оно действует сутки.`
                  : 'Почта не указана. Без неё забытый пароль придётся сбрасывать через администратора.'}
            </p>
            {account?.pending_email && (
              <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-md)' }}>
                <Button fill="outline" block loading={busy === 'resend'} disabled={!!busy} onClick={resend}>
                  Отправить письмо ещё раз
                </Button>
              </div>
            )}
            <Form layout="vertical" mode="card">
              <Form.Item label="Адрес почты">
                <Input type="email" value={value} onChange={setEmail} placeholder="name@example.com" clearable maxLength={254} autoComplete="email" />
              </Form.Item>
              <Form.Item label="Текущий пароль" description={asked && !password ? <FieldError message="Введите текущий пароль" /> : 'Почтой можно вернуть доступ к аккаунту, поэтому менять её можно только с паролем'}>
                <Input type="password" value={password} onChange={setPassword} placeholder="Пароль от Petzy" autoComplete="current-password" />
              </Form.Item>
            </Form>
            <div className="safe-area-padding" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)', marginTop: 'var(--spacing-lg)' }}>
              <Button block color="primary" size="large" data-enter-submit loading={busy === 'save'} disabled={!!busy || !value.trim()} onClick={() => save(value.trim(), 'save')}>
                Сохранить и подтвердить
              </Button>
              {current && (
                <Button block fill="none" color="danger" loading={busy === 'remove'} disabled={!!busy} onClick={() => save('', 'remove')}>
                  Удалить почту
                </Button>
              )}
              <Button block fill="none" onClick={() => goBack(navigate, '/settings')}>
                Назад
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

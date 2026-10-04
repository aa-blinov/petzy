import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Form, Input } from 'antd-mobile';
import { accountService } from '../services/account.service';
import { FieldError } from '../components/FieldError';
import { useTouched } from '../hooks/useTouched';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { goBack } from '../utils/navigation';

/** Настройки → «Пароль». Other devices are signed out; this one stays in. */
export function AccountPassword() {
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const { touch, shows } = useTouched(submitted);
  const [busy, setBusy] = useState(false);

  const nextError = next.length < 8 ? 'Не короче 8 символов' : null;
  const repeatError = repeat !== next ? 'Пароли не совпадают' : null;

  const save = async () => {
    setSubmitted(true);
    if (!current || nextError || repeatError) return;
    setBusy(true);
    try {
      await accountService.changePassword(current, next);
      showToast.success('Пароль изменён. На других устройствах нужно будет войти заново', { duration: 3500 });
      goBack(navigate, '/settings');
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось сменить пароль'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Пароль</h1>
        </div>
        <Form layout="vertical" mode="card">
          <Form.Item label="Текущий пароль" description={shows('current') && !current ? <FieldError message="Введите текущий пароль" /> : undefined}>
            <Input type="password" value={current} onChange={setCurrent} onBlur={touch('current')} autoComplete="current-password" placeholder="Текущий пароль" />
          </Form.Item>
          <Form.Item label="Новый пароль" description={shows('next') && nextError ? <FieldError message={nextError} /> : 'Не короче 8 символов'}>
            <Input type="password" value={next} onChange={setNext} onBlur={touch('next')} autoComplete="new-password" placeholder="Новый пароль" />
          </Form.Item>
          <Form.Item label="Новый пароль ещё раз" description={shows('repeat') && repeatError ? <FieldError message={repeatError} /> : undefined}>
            <Input type="password" value={repeat} onChange={setRepeat} onBlur={touch('repeat')} autoComplete="new-password" placeholder="Повторите новый пароль" />
          </Form.Item>
        </Form>
        <div className="safe-area-padding form-actions">
          <Button block color="primary" size="large" data-enter-submit loading={busy} disabled={busy} onClick={save}>
            Сменить пароль
          </Button>
          <Button block fill="none" onClick={() => goBack(navigate, '/settings')}>
            Отмена
          </Button>
        </div>
      </div>
    </div>
  );
}

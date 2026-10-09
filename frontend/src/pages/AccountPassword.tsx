import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Form, Input } from 'antd-mobile';
import { isAxiosError } from 'axios';
import { accountService } from '../services/account.service';
import { FieldError } from '../components/FieldError';
import { useTouched } from '../hooks/useTouched';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { goBack } from '../utils/navigation';
import { onInvalidSubmit } from '../utils/formErrors';
import { passwordProblem, retryNote, useRetryLock } from '../utils/authForms';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';

/** Настройки → «Пароль». Other devices are signed out; this one stays in. */
export function AccountPassword() {
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [wrongCurrent, setWrongCurrent] = useState(false);
  const { touch, shows } = useTouched(submitted);
  const [busy, setBusy] = useState(false);
  // The server allows ten password changes an hour. A refused one used to be
  // a bare toast with no word about waiting, and the next attempt would be
  // refused too, so the wait is said and the button is closed for it, the way
  // the sign-in screen does.
  const { left: retryLeft, lock: lockAfterRefusal } = useRetryLock();
  const locked = retryLeft > 0;
  // Three typed passwords are three words of effort: the question before
  // leaving, the way every other form here does it.
  const { dialog: leaveDialog, release } = useUnsavedChangesGuard(!!current || !!next || !!repeat);

  const nextError = passwordProblem(next);
  const repeatError = repeat !== next ? 'Пароли не совпадают' : null;

  const leave = (afterSave = false) => {
    // Only a finished save leaves without a word; a cancel that throws the
    // typed passwords away asks, like every other way out.
    if (afterSave) release();
    goBack(navigate, '/settings');
  };

  const save = async () => {
    setSubmitted(true);
    if (!current || nextError || repeatError) {
      // What a failed save does everywhere else: the first message in view, its field in focus, the count said aloud.
      onInvalidSubmit({
        ...(!current && { current: { type: 'required', message: 'Введите текущий пароль' } }),
        ...(nextError && { next: { type: 'minLength', message: nextError } }),
        ...(repeatError && { repeat: { type: 'validate', message: repeatError } }),
      });
      return;
    }
    if (locked) return;
    setBusy(true);
    try {
      await accountService.changePassword(current, next);
      showToast.success('Пароль изменён. На других устройствах нужно будет войти заново', { duration: 3500 });
      leave(true);
    } catch (err) {
      lockAfterRefusal(err);
      // Only a refused current password is that; a dead connection isn't.
      if (isAxiosError<{ code?: string }>(err) && err.response?.data?.code === 'account_wrong_password') {
        setWrongCurrent(true);
      }
      showToast.failure(getApiErrorMessage(err, 'Не удалось сменить пароль'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 500, margin: 0 }}>Пароль</h1>
          <p style={{ margin: 'var(--spacing-xs) 0 0', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
            После смены пароля на других устройствах придётся войти заново
          </p>
        </div>
        <Form layout="vertical" mode="card">
          <Form.Item label="Текущий пароль" description={shows('current') && !current ? <FieldError message="Введите текущий пароль" /> : undefined}>
            <Input type="password" value={current} onChange={setCurrent} onBlur={touch('current')} autoComplete="current-password" placeholder="Текущий пароль" />
          </Form.Item>
          <Form.Item label="Новый пароль" description={shows('next') && nextError ? <FieldError message={nextError} /> : 'Не короче 8 символов, хотя бы три разных и не логин'}>
            <Input type="password" value={next} onChange={setNext} onBlur={touch('next')} autoComplete="new-password" placeholder="Новый пароль" />
          </Form.Item>
          <Form.Item label="Новый пароль ещё раз" description={shows('repeat') && repeatError ? <FieldError message={repeatError} /> : undefined}>
            <Input type="password" value={repeat} onChange={setRepeat} onBlur={touch('repeat')} autoComplete="new-password" placeholder="Повторите новый пароль" />
          </Form.Item>
          {/* The way out, but only once the save has refused: a question
              about the current password under an empty form is one nobody
              asked. */}
          {wrongCurrent && (
            <p style={{ margin: '0 0 var(--spacing-md)', fontSize: 'var(--text-sm)' }}>
              <Link to="/forgot-password" className="tap-link" style={{ color: 'var(--app-accent-deep)', fontWeight: 500 }}>
                Забыли текущий пароль?
              </Link>
            </p>
          )}
        </Form>
        <div className="safe-area-padding form-actions">
          <Button block color="primary" size="large" data-enter-submit loading={busy} disabled={busy || locked} onClick={save}>
            {locked ? `Ещё ${retryLeft} с` : 'Сменить пароль'}
          </Button>
          {retryNote(retryLeft) && (
            <p role="status" style={{ margin: 0, fontSize: 'var(--text-xs)', lineHeight: 1.4, textAlign: 'center', color: 'var(--app-text-secondary)' }}>
              {retryNote(retryLeft)}
            </p>
          )}
          <Button block fill="none" onClick={() => leave()}>
            Отмена
          </Button>
        </div>
      </div>
      {leaveDialog}
    </div>
  );
}

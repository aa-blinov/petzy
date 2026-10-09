import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button, Dialog, Form, Input } from 'antd-mobile';
import { isAxiosError } from 'axios';
import { accountService, type DeletionPet } from '../services/account.service';
import { useAuth } from '../hooks/useAuth';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { hapticFeedback } from '../utils/haptic';
import { goBack } from '../utils/navigation';
import { FieldError } from '../components/FieldError';
import { onInvalidSubmit } from '../utils/formErrors';

/** The push subscription dies with the account on the server; drop this
    browser's copy too, so it doesn't sit there subscribed to nothing. */
async function forgetPushSubscription() {
  try {
    const registration = await navigator.serviceWorker?.getRegistration();
    const subscription = await registration?.pushManager?.getSubscription();
    await subscription?.unsubscribe();
  } catch {
    /* nothing to clean up */
  }
}

function PetGroup({ title, note, pets, detail }: {
  title: string;
  note: string;
  pets: DeletionPet[];
  detail?: (pet: DeletionPet) => string;
}) {
  if (pets.length === 0) return null;
  return (
    <section style={{ marginTop: 'var(--spacing-lg)' }}>
      <h2 className="section-header" style={{ marginBottom: 'var(--spacing-xs)' }}>{title}</h2>
      <p style={{ margin: '0 0 var(--spacing-sm)', color: 'var(--app-text-secondary)', fontSize: 'var(--text-sm)' }}>{note}</p>
      <div className="card-soft" style={{ overflow: 'hidden' }}>
        {pets.map((pet, i) => (
          <div
            key={pet.id}
            style={{
              padding: 'var(--spacing-sm) var(--spacing-md)',
              borderTop: i === 0 ? 'none' : '1px solid var(--app-border-color)',
            }}
          >
            <div style={{ color: 'var(--app-text-color)', fontWeight: 500 }}>{pet.name}</div>
            {detail && (
              <div style={{ color: 'var(--app-text-secondary)', fontSize: 'var(--text-sm)' }}>{detail(pet)}</div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

/** Настройки → «Удалить аккаунт»: what happens to each pet, then the password. */
export function AccountDelete() {
  const navigate = useNavigate();
  const { username, logout } = useAuth();
  const [password, setPassword] = useState('');
  const [confirmVisible, setConfirmVisible] = useState(false);
  const [asked, setAsked] = useState(false);
  const [busy, setBusy] = useState(false);
  // The link broke after the answer was on its way: whether the account is
  // gone is unknown, and saying «не удалось удалить» would be a guess.
  const [cutOff, setCutOff] = useState(false);
  const { data: preview, isLoading, isError, refetch } = useQuery({
    queryKey: ['account', 'deletion'],
    queryFn: () => accountService.deletionPreview(),
    staleTime: 0,
  });

  const ask = () => {
    setAsked(true);
    if (!password) {
      onInvalidSubmit({ password: { type: 'required', message: 'Введите пароль' } });
      return;
    }
    hapticFeedback('medium');
    setConfirmVisible(true);
  };

  const remove = async () => {
    setBusy(true);
    try {
      await accountService.deleteAccount(password);
      setConfirmVisible(false);
      // Off the screen at once: the account is gone, and a form that is still
      // asking for its password a second longer reads as if it weren't. The
      // push unsubscribe is this browser's own tidying up and has no word to
      // give anybody, so it is left to finish on its own.
      void forgetPushSubscription();
      showToast.success('Аккаунт удалён', { duration: 3000 });
      await logout();
    } catch (err) {
      setConfirmVisible(false);
      if (isAxiosError(err) && !err.response) {
        // The request left and no answer came back: the deletion may well
        // have happened. The way out is to try to sign in, not to press
        // «удалить» once more.
        setCutOff(true);
        showToast.failure('Связь прервалась. Проверьте, удалился ли аккаунт: войдите заново', { duration: 5000 });
      } else {
        showToast.failure(getApiErrorMessage(err, 'Не удалось удалить аккаунт'));
      }
    } finally {
      setBusy(false);
    }
  };

  const keepsRecords = !!preview && (preview.transferred.length > 0 || preview.left.length > 0);
  // What the confirmation says, in the words of the plan above it: pets
  // gone with their records, pets handed over, access ended.
  const summary = preview
    ? `Удалятся: ${preview.deleted.length ? preview.deleted.map(p => `«${p.name}»`).join(', ') : 'ничьи питомцы'}, вместе с записями, лекарствами и документами. ` +
      (preview.transferred.length ? `Перейдут другим: ${preview.transferred.map(p => `«${p.name}»`).join(', ')}. ` : '') +
      (preview.left.length ? `Пропадёт доступ к ${preview.left.length} питомцам других людей.` : '')
    : '';

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding">
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 500, margin: 0 }}>
            Удаление аккаунта
          </h1>

          {isLoading && <LoadingSpinner />}
          {isError && (
            <>
              <p style={{ color: 'var(--app-text-secondary)' }}>
                Не удалось узнать, что станет с питомцами
              </p>
              {/* Asked to leave the screen and come back, with the reason
                  already known: the question is one answer away. */}
              <Button
                block
                color="primary"
                fill="outline"
                style={{ marginTop: 'var(--spacing-sm)' }}
                onClick={() => { void refetch(); }}
              >
                Повторить
              </Button>
            </>
          )}

          {cutOff && (
            <div style={{ marginTop: 'var(--spacing-md)' }}>
              <p style={{ color: 'var(--app-text-color)', margin: '0 0 var(--spacing-sm)' }}>
                Связь оборвалась в момент удаления, так что аккаунт, возможно, уже удалён. Попробуйте войти: если не выйдет,
                напишите администратору Petzy
              </p>
              <Button block color="primary" size="large" onClick={() => navigate('/login')}>
                Войти
              </Button>
            </div>
          )}

          {preview && !preview.can_delete && (
            <p style={{ color: 'var(--app-text-secondary)', marginTop: 'var(--spacing-md)' }}>
              Аккаунт администратора удалить нельзя: без него никто не сможет управлять Petzy
            </p>
          )}

          {preview?.can_delete && (
            <>
              <p style={{ color: 'var(--app-text-color)', marginTop: 'var(--spacing-md)', marginBottom: 0 }}>
                Аккаунт {username} удалится насовсем, восстановить его не получится
              </p>

              <PetGroup
                title="Удалятся"
                note="Их больше никто не ведёт, поэтому они удалятся вместе с записями, лекарствами и документами"
                pets={preview.deleted}
              />
              <PetGroup
                title="Перейдут другим"
                note="Вы делились ими, поэтому они останутся со всей историей у того, кому вы дали доступ первым"
                pets={preview.transferred}
                detail={pet => `Владельцем станет ${pet.new_owner}`}
              />
              <PetGroup
                title="Пропадёт доступ"
                note="Этими питомцами делятся с вами. У владельцев они останутся"
                pets={preview.left}
                detail={pet => `Питомец ${pet.owner}`}
              />
              {keepsRecords && (
                <p style={{ color: 'var(--app-text-secondary)', fontSize: 'var(--text-sm)', marginTop: 'var(--spacing-md)' }}>
                  Записи, которые вы добавили этим питомцам, останутся, но без вашего имени
                </p>
              )}
            </>
          )}
        </div>

        {preview?.can_delete && (
          <Form layout="vertical" mode="card" style={{ marginTop: 'var(--spacing-lg)' }}>
            <Form.Item label="Пароль" description={asked && !password ? <FieldError message="Введите пароль" /> : 'Чтобы подтвердить, что это вы'}>
              <Input
                id="delete-account-password"
                type="password"
                value={password}
                onChange={setPassword}
                autoComplete="current-password"
                placeholder="Текущий пароль"
              />
            </Form.Item>
          </Form>
        )}

        <div
          className="safe-area-padding form-actions"
        >
          {preview?.can_delete && (
            <Button block color="danger" size="large" loading={busy} disabled={busy} onClick={ask}>
              Удалить аккаунт
            </Button>
          )}
          <Button block fill="none" onClick={() => goBack(navigate, '/settings')}>
            {preview?.can_delete ? 'Отмена' : 'Назад'}
          </Button>
        </div>
      </div>

      <Dialog
        visible={confirmVisible}
        title="Удалить аккаунт?"
        content={summary || 'Это нельзя отменить'}
        onClose={() => setConfirmVisible(false)}
        getContainer={() => document.body}
        actions={[
          { key: 'confirm', text: 'Удалить', danger: true, bold: true, disabled: busy, onClick: remove },
          { key: 'cancel', text: 'Отмена', onClick: () => setConfirmVisible(false) },
        ]}
      />
    </div>
  );
}

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button, Dialog, Form, Input } from 'antd-mobile';
import { accountService, type DeletionPet } from '../services/account.service';
import { useAuth } from '../hooks/useAuth';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { hapticFeedback } from '../utils/haptic';
import { goBack } from '../utils/navigation';

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
  const [busy, setBusy] = useState(false);
  const { data: preview, isLoading, isError } = useQuery({
    queryKey: ['account', 'deletion'],
    queryFn: () => accountService.deletionPreview(),
    staleTime: 0,
  });

  const ask = () => {
    if (!password) {
      showToast.failure('Введите пароль');
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
      await forgetPushSubscription();
      showToast.success('Аккаунт удалён', { duration: 3000 });
      await logout();
    } catch (err) {
      setConfirmVisible(false);
      showToast.failure(getApiErrorMessage(err, 'Не удалось удалить аккаунт'));
    } finally {
      setBusy(false);
    }
  };

  const keepsRecords = !!preview && (preview.transferred.length > 0 || preview.left.length > 0);

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding">
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
            Удаление аккаунта
          </h1>

          {isLoading && <LoadingSpinner />}
          {isError && (
            <p style={{ color: 'var(--app-text-secondary)' }}>
              Не удалось узнать, что станет с питомцами. Попробуйте открыть страницу ещё раз.
            </p>
          )}

          {preview && !preview.can_delete && (
            <p style={{ color: 'var(--app-text-secondary)', marginTop: 'var(--spacing-md)' }}>
              Аккаунт администратора удалить нельзя: без него никто не сможет управлять Petzy.
            </p>
          )}

          {preview?.can_delete && (
            <>
              <p style={{ color: 'var(--app-text-color)', marginTop: 'var(--spacing-md)', marginBottom: 0 }}>
                Аккаунт {username} удалится насовсем, восстановить его не получится.
              </p>

              <PetGroup
                title="Удалятся"
                note="Их больше никто не ведёт, поэтому они удалятся вместе с записями, лекарствами и документами."
                pets={preview.deleted}
              />
              <PetGroup
                title="Перейдут другим"
                note="Вы делились ими, поэтому они останутся со всей историей у того, кому вы дали доступ первым."
                pets={preview.transferred}
                detail={pet => `Владельцем станет ${pet.new_owner}`}
              />
              <PetGroup
                title="Пропадёт доступ"
                note="Этими питомцами делятся с вами. У владельцев они останутся."
                pets={preview.left}
                detail={pet => `Питомец ${pet.owner}`}
              />
              {keepsRecords && (
                <p style={{ color: 'var(--app-text-secondary)', fontSize: 'var(--text-sm)', marginTop: 'var(--spacing-md)' }}>
                  Записи, которые вы добавили этим питомцам, останутся, но без вашего имени.
                </p>
              )}
            </>
          )}
        </div>

        {preview?.can_delete && (
          <Form layout="vertical" mode="card" style={{ marginTop: 'var(--spacing-lg)' }}>
            <Form.Item label="Пароль" description="Чтобы подтвердить, что это вы">
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
          className="safe-area-padding"
          style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)', marginTop: 'var(--spacing-lg)' }}
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
        content="Это нельзя отменить."
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

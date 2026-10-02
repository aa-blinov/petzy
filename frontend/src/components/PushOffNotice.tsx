import { useEffect, useState } from 'react';
import { BellOff } from 'lucide-react';
import { Button } from 'antd-mobile';
import { getPushSubscriptionState, needsHomeScreenForPush, subscribeToPush, type PushSupportState } from '../utils/pushNotifications';
import { showToast } from '../utils/toast';

/**
 * «Напоминания выключены на этом телефоне»: said on the screen where doses are, with the way to turn them on. A person
 * invited by the family has no onboarding that asks, and a course that promises «Petzy напомнит» on a phone that cannot
 * hear it is a missed dose. Nothing is shown when push works here.
 */
export function PushOffNotice() {
  const [state, setState] = useState<PushSupportState | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    getPushSubscriptionState().then((s) => live && setState(s)).catch(() => live && setState(null));
    return () => {
      live = false;
    };
  }, []);
  if (!state || state === 'on') return null;
  const homeScreen = state === 'unsupported' && needsHomeScreenForPush();
  if (state === 'unsupported' && !homeScreen) return null;

  const turnOn = async () => {
    setBusy(true);
    try {
      await subscribeToPush();
      setState('on');
      showToast.success('Напоминания включены на этом телефоне');
    } catch (err) {
      showToast.failure(err instanceof Error ? err.message : 'Не удалось включить напоминания');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card-soft" role="note" style={{ padding: 'var(--spacing-md)', display: 'grid', gap: 'var(--spacing-sm)' }}>
      <div style={{ display: 'flex', gap: 'var(--spacing-sm)', alignItems: 'flex-start', color: 'var(--app-text-primary)' }}>
        <BellOff size={18} strokeWidth={2} aria-hidden style={{ flexShrink: 0, marginTop: 2 }} />
        <span>
          {state === 'off' && 'Напоминания о приёмах выключены на этом телефоне: лекарство не напомнит о себе.'}
          {state === 'denied' && 'Уведомления заблокированы в настройках браузера, поэтому напоминания о приёмах не придут. Разрешите их для Petzy в настройках браузера или телефона.'}
          {homeScreen && 'На iPhone напоминания работают, когда Petzy добавлен на экран «Домой». Добавьте его оттуда и включите напоминания в Настройках.'}
        </span>
      </div>
      {state === 'off' && (
        <Button size="small" color="primary" loading={busy} onClick={turnOn}>
          Включить напоминания
        </Button>
      )}
    </div>
  );
}

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { isAxiosError } from 'axios';
import { Dialog, Switch } from 'antd-mobile';
import { Bell, Moon, SlidersHorizontal, LayoutGrid, LogOut, PawPrint, Sparkles, Users } from 'lucide-react';

import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../hooks/useAuth';
import { useAdmin } from '../hooks/useAdmin';
import { SettingsRow } from '../components/SettingsRow';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import {
  getPushSubscriptionState,
  subscribeToPush,
  unsubscribeFromPush,
  type PushSupportState,
} from '../utils/pushNotifications';

export function Settings() {
  const navigate = useNavigate();
  const { theme, setTheme, isDark } = useTheme();
  const { logout } = useAuth();
  const { isAdmin } = useAdmin();
  const [logoutDialogVisible, setLogoutDialogVisible] = useState(false);

  // null while the initial serviceWorker.ready + getSubscription() check
  // is in flight — the row renders once that resolves, since flashing
  // "off" then immediately "on" reads as a bug rather than a toggle.
  const [pushState, setPushState] = useState<PushSupportState | null>(null);
  const [pushBusy, setPushBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getPushSubscriptionState().then((state) => {
      if (!cancelled) setPushState(state);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const handlePushToggle = async (checked: boolean) => {
    setPushBusy(true);
    try {
      if (checked) {
        await subscribeToPush();
        setPushState('on');
        showToast.success('Уведомления включены');
      } else {
        await unsubscribeFromPush();
        setPushState('off');
        showToast.success('Уведомления отключены');
      }
    } catch (error) {
      // pushNotifications.ts throws plain Errors with an already
      // user-facing message (unsupported browser, permission denied,
      // etc.); getApiErrorMessage only unwraps axios errors (e.g. the
      // backend's "push_not_configured"), so a plain Error needs its
      // own .message instead of falling through to a generic fallback.
      const message = isAxiosError(error)
        ? getApiErrorMessage(error, 'Не удалось изменить настройку уведомлений')
        : error instanceof Error
          ? error.message
          : 'Не удалось изменить настройку уведомлений';
      showToast.failure(message);
    } finally {
      setPushBusy(false);
    }
  };

  const confirmLogout = async () => {
    setLogoutDialogVisible(false);
    // useAuth.logout() handles the navigate('/login', {replace:true}) itself,
    // so we don't need to navigate again here.
    await logout();
  };

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1
            className="display-headline"
            style={{ fontSize: '28px', margin: 0 }}
          >
            Настройки
          </h1>
        </div>

        <div className="safe-area-padding">
          {/* Section: Внешний вид */}
          <h3 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>
            Внешний вид
          </h3>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<Moon size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Тёмная тема"
              description={
                theme === 'system'
                  ? 'Следует за настройками системы'
                  : isDark
                    ? 'Включена'
                    : 'Выключена'
              }
              control={
                <Switch
                  checked={isDark}
                  onChange={(checked) => setTheme(checked ? 'dark' : 'light')}
                />
              }
            />
            {/* Always visible with its own on/off state — this used to be
                a plain clickable row that only showed up while OFF and
                vanished the moment you turned it on, with no way to see
                (or turn back off) the setting it had just applied. */}
            <SettingsRow
              icon={<SlidersHorizontal size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Следовать за системой"
              description="Авто-переключение день/ночь"
              control={
                <Switch
                  checked={theme === 'system'}
                  onChange={(checked) => setTheme(checked ? 'system' : (isDark ? 'dark' : 'light'))}
                />
              }
            />
          </div>

          {/* Section: Push-уведомления. The row itself only ever shows
              a switch — "unsupported"/"denied" states disable it with an
              explanatory description instead of hiding the row, so a
              user on an unsupported browser at least understands why
              it's not available rather than wondering if it's missing. */}
          <h3
            className="section-header"
            style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
          >
            Уведомления
          </h3>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<Bell size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Напоминания о приёме лекарств"
              description={
                pushState === 'unsupported'
                  ? 'Этот браузер не поддерживает push-уведомления'
                  : pushState === 'denied'
                    ? 'Заблокированы в настройках браузера'
                    : pushState === 'on'
                      ? 'Включены на этом устройстве'
                      : 'Выключены на этом устройстве'
              }
              control={
                <Switch
                  checked={pushState === 'on'}
                  disabled={pushState === null || pushState === 'unsupported' || pushState === 'denied' || pushBusy}
                  onChange={handlePushToggle}
                />
              }
            />
          </div>

          {/* Section: Pets
              The only route to /pets used to be the "Управление
              питомцами" button inside the navbar's pet picker, and that
              picker only renders from the second pet onwards — so a
              household with exactly one pet had no way to add a second
              one, edit it, or delete it. This row is always reachable,
              which also lets the navbar picker stay a pure switcher. */}
          <h3
            className="section-header"
            style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
          >
            Питомцы
          </h3>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<PawPrint size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Мои питомцы"
              description="Добавить, изменить или удалить питомца"
              chevron
              onClick={() => navigate('/pets')}
            />
          </div>

          {/* Section: Defaults */}
          <h3
            className="section-header"
            style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
          >
            Значения по умолчанию
          </h3>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<SlidersHorizontal size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Настройки форм"
              description="Дефолтные значения и единицы измерения"
              chevron
              onClick={() => navigate('/form-defaults')}
            />
          </div>

          {/* Section: Dashboard */}
          <h3
            className="section-header"
            style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
          >
            Дашборд
          </h3>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<LayoutGrid size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Порядок тайлов"
              description="Какие записи видны и в каком порядке"
              chevron
              onClick={() => navigate('/tiles-settings')}
            />
          </div>

          {/* Section: Event types — the "factory": builtin types can be
              relabelled/recolored here too, and custom ones created from
              scratch with their own fields. */}
          <h3
            className="section-header"
            style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
          >
            События
          </h3>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<Sparkles size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Типы событий"
              description="Свои типы записей со своими полями"
              chevron
              onClick={() => navigate('/event-types')}
            />
          </div>

          {/* Section: Admin — used to be its own bottom-tab entry, shown
              only to admins. That meant a whole tab-bar slot (and its own
              full-page layout) existed purely to hold one link, visible to
              a fraction of users. Folding it in here as a settings row
              needs no dedicated chrome and matches how every other
              secondary screen (pets, form defaults, event types) is
              reached. */}
          {isAdmin && (
            <>
              <h3
                className="section-header"
                style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
              >
                Администрирование
              </h3>
              <div className="card-soft" style={{ overflow: 'hidden' }}>
                <SettingsRow
                  icon={<Users size={18} strokeWidth={2} style={{ display: 'block' }} />}
                  label="Пользователи"
                  description="Управление учётными записями"
                  chevron
                  onClick={() => navigate('/admin')}
                />
              </div>
            </>
          )}

          {/* Logout — destructive but tucked away at the bottom, not a giant red block */}
          <button
            type="button"
            onClick={() => setLogoutDialogVisible(true)}
            style={{
              marginTop: 'var(--spacing-xl)',
              padding: 'var(--spacing-md)',
              width: '100%',
              background: 'transparent',
              border: 'none',
              color: 'var(--app-text-secondary)',
              fontFamily: 'var(--font-display)',
              fontSize: 'var(--text-sm)',
              cursor: 'pointer',
            }}
          >
            <LogOut size={16} strokeWidth={2} style={{ verticalAlign: 'middle', marginRight: 8, display: 'inline-block' }} />
            Выйти из аккаунта
          </button>
        </div>
      </div>

      <Dialog
        visible={logoutDialogVisible}
        title="Выход из аккаунта"
        content="Вы уверены, что хотите выйти?"
        closeOnAction
        onClose={() => setLogoutDialogVisible(false)}
        actions={[
          [
            // Destructive action first, cancel second — antd stacks
            // dialog actions vertically, and the four delete dialogs
            // (курс, питомец, пользователь, запись) all put the
            // destructive one on top. This one had them reversed, so
            // the dangerous button changed position between screens.
            { key: 'confirm', text: 'Выйти', bold: true, danger: true, onClick: confirmLogout },
            { key: 'cancel', text: 'Отмена', onClick: () => setLogoutDialogVisible(false) },
          ],
        ]}
      />
    </div>
  );
}

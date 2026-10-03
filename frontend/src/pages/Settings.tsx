import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { isAxiosError } from 'axios';
import { Dialog, Switch } from 'antd-mobile';
import { Bell, CircleHelp, Compass, Download, History as HistoryIcon, KeyRound, Mail, SlidersHorizontal, LayoutGrid, Palette, LogOut, PawPrint, ShieldCheck, Sparkles, Trash2, Users } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { accountService, ACCOUNT_QUERY_KEY } from '../services/account.service';

import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../hooks/useAuth';
import { useAdmin } from '../hooks/useAdmin';
import { SettingsRow } from '../components/SettingsRow';
import { Segmented } from '../components/Segmented';
import { ExportModal, ALL_TYPES } from '../components/ExportModal';
import { usePet } from '../hooks/usePet';
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
  const { selectedPetId } = usePet();
  const [exportVisible, setExportVisible] = useState(false);
  const { theme, setTheme, isDark } = useTheme();
  const { logout } = useAuth();
  const { isAdmin } = useAdmin();
  const { data: account } = useQuery({ queryKey: ACCOUNT_QUERY_KEY, queryFn: () => accountService.get() });
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
          <h2 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>
            Внешний вид
          </h2>
          <div className="card-soft" style={{ padding: 'var(--spacing-md)', display: 'grid', gap: 'var(--spacing-sm)' }}>
            {/* One choice of three, where there were two switches that had to be read together: «Тёмная тема» off and
                «Следовать за системой» on said nothing about which theme was showing. */}
            <div className="setting-row__label" id="theme-label">Тема оформления</div>
            <Segmented
              label="Тема оформления"
              value={theme}
              options={[
                { value: 'light', label: 'Светлая' },
                { value: 'dark', label: 'Тёмная' },
                { value: 'system', label: 'Как в системе' },
              ]}
              onChange={setTheme}
            />
            {theme === 'system' && (
              <div className="setting-row__description">Сейчас {isDark ? 'тёмная' : 'светлая'}, как на телефоне</div>
            )}
          </div>

          {/* Section: Push-уведомления. The row itself only ever shows
              a switch — "unsupported"/"denied" states disable it with an
              explanatory description instead of hiding the row, so a
              user on an unsupported browser at least understands why
              it's not available rather than wondering if it's missing. */}
          <h2
            className="section-header"
            style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
          >
            Уведомления
          </h2>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<Bell size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Push-уведомления"
              description={
                pushState === 'unsupported'
                  ? 'Этот браузер не поддерживает push-уведомления'
                  : pushState === 'denied'
                    ? 'Заблокированы в настройках браузера'
                    : pushState === 'on'
                      ? 'Напоминания включены на этом устройстве: лекарства, прививки и обработки, документы, необычные показатели'
                      : 'Лекарства, прививки и обработки, документы, необычные показатели'
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

          {/* Section: Account. The email is what a forgotten password is
              recovered with, so its state is on the row itself. */}
          <h2
            className="section-header"
            style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
          >
            Аккаунт
          </h2>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<Mail size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Почта"
              description={
                !account
                  ? ' '
                  : account.pending_email
                    ? `${account.email_verified && account.email ? `Подтверждена: ${account.email} ` : ''}Ждёт подтверждения: ${account.pending_email}`
                    : account.email_verified
                      ? account.email
                      : 'Не указана. Нужна, чтобы восстановить пароль'
              }
              chevron
              onClick={() => navigate('/settings/email')}
            />
            <SettingsRow
              icon={<KeyRound size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Пароль"
              description={account ? `Логин: ${account.username}` : ' '}
              chevron
              onClick={() => navigate('/settings/password')}
            />
            {!isAdmin && (
              <SettingsRow
                icon={<Trash2 size={18} strokeWidth={2} style={{ display: 'block' }} />}
                label="Удалить аккаунт"
                description="Насовсем, вместе с данными"
                danger
                chevron
                onClick={() => navigate('/settings/delete-account')}
              />
            )}
          </div>

          {/* Section: Pets
              The only route to /pets used to be the "Управление
              питомцами" button inside the navbar's pet picker, and that
              picker only renders from the second pet onwards — so a
              household with exactly one pet had no way to add a second
              one, edit it, or delete it. This row is always reachable,
              which also lets the navbar picker stay a pure switcher. */}
          <h2
            className="section-header"
            style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
          >
            Питомцы
          </h2>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<PawPrint size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Мои питомцы"
              description="Добавить, изменить или удалить питомца"
              chevron
              onClick={() => navigate('/pets')}
            />
          </div>

          {/* Section: Records. The history screen is not a tab: this row and the card's «Вес» lead to it. */}
          <h2
            className="section-header"
            style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
          >
            Записи
          </h2>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<HistoryIcon size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="История записей"
              description="Всё за всё время, фильтр по типу и графики"
              chevron
              onClick={() => navigate('/history')}
            />
            <SettingsRow
              icon={<Download size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Экспорт записей"
              description="Скачать записи питомца таблицей"
              chevron
              onClick={() => (selectedPetId ? setExportVisible(true) : showToast.info('Сначала выберите питомца'))}
            />
          </div>

          {/* Section: New records: what the «+» offers and what a new form starts with, both for the selected pet. */}
          <h2
            className="section-header"
            style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
          >
            Новые записи
          </h2>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<LayoutGrid size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Кнопки быстрого добавления"
              description="Какие записи видны в окне «+» и в каком порядке"
              chevron
              onClick={() => navigate('/tiles-settings')}
            />
            <SettingsRow
              icon={<SlidersHorizontal size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Значения по умолчанию"
              description="Что подставляется в новые записи выбранного питомца"
              chevron
              onClick={() => navigate('/form-defaults')}
            />
          </div>

          {/* Section: the pet's card: how its page shows it. */}
          <h2
            className="section-header"
            style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
          >
            Питомец
          </h2>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<Palette size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Оформление питомца"
              description="Образ, цвет, шрифт имени, рамка фото и фон ленты"
              chevron
              onClick={() => navigate('/pet-look')}
            />
          </div>

          {/* Section: Event types — the "factory": builtin types can be
              relabelled/recolored here too, and custom ones created from
              scratch with their own fields. */}
          <h2
            className="section-header"
            style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
          >
            События
          </h2>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<Sparkles size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Типы событий"
              description="Свои типы записей со своими полями"
              chevron
              onClick={() => navigate('/event-types')}
            />
          </div>

          <h2
            className="section-header"
            style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
          >
            О приложении
          </h2>
          <div className="card-soft" style={{ overflow: 'hidden' }}>
            <SettingsRow
              icon={<Compass size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Знакомство с Petzy"
              description="Показать вводные экраны ещё раз"
              chevron
              onClick={() => navigate('/welcome?replay=1')}
            />
            <SettingsRow
              icon={<CircleHelp size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Справка"
              description="Частые вопросы и как устроен каждый экран"
              chevron
              onClick={() => navigate('/help')}
            />
            <SettingsRow
              icon={<ShieldCheck size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Политика конфиденциальности"
              description="Какие данные хранятся и где"
              chevron
              onClick={() => navigate('/privacy')}
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
              <h2
                className="section-header"
                style={{ marginTop: 'var(--spacing-xl)', marginBottom: 'var(--spacing-sm)' }}
              >
                Администрирование
              </h2>
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
              minHeight: 'var(--touch-min)',
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

      {selectedPetId && <ExportModal visible={exportVisible} onClose={() => setExportVisible(false)} petId={selectedPetId} defaultType={ALL_TYPES} />}
    </div>
  );
}

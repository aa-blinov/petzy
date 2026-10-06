import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { isAxiosError } from 'axios';
import { Dialog, Switch } from 'antd-mobile';
import { Bell, CircleHelp, HeartPulse, Link2, Compass, Download, History as HistoryIcon, KeyRound, Mail, SlidersHorizontal, LayoutGrid, Palette, LogOut, PawPrint, ShieldCheck, Sparkles, Trash2, UserRound, Users } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { accountService, ACCOUNT_QUERY_KEY, type Account } from '../services/account.service';

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
  needsHomeScreenForPush,
  subscribeToPush,
  unsubscribeFromPush,
  type PushSupportState,
} from '../utils/pushNotifications';

/** A titled card of rows: every group of the settings looks the same and sits the same distance from the one above. */
function Group({ title, first = false, children }: { title: string; first?: boolean; children: ReactNode }) {
  return (
    <section style={{ marginTop: first ? 0 : 'var(--spacing-xl)' }}>
      <h2 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>
        {title}
      </h2>
      <div className="card-soft" style={{ overflow: 'hidden' }}>
        {children}
      </div>
    </section>
  );
}

export function Settings() {
  const navigate = useNavigate();
  const { selectedPetId, getSelectedPet, isLoading: petsLoading } = usePet();
  const [exportVisible, setExportVisible] = useState(false);
  const { theme, setTheme } = useTheme();
  const { logout, username } = useAuth();
  const { isAdmin } = useAdmin();
  const { data: account, isLoading: accountLoading, isError: accountFailed } = useQuery({
    queryKey: ACCOUNT_QUERY_KEY,
    queryFn: () => accountService.get(),
  });
  const [logoutDialogVisible, setLogoutDialogVisible] = useState(false);

  // A row about the account says what it knows, and says that it doesn't know yet. While the request is in
  // flight the description was a single space: an empty line under a label, which reads as a screen that
  // failed to load rather than one still loading.
  const accountText = (ready: (account: Account) => string) =>
    accountFailed ? 'Не удалось загрузить' : !account || accountLoading ? 'Загружаем' : ready(account);

  // A row that acts on one pet says what it can do only when that pet is known. While the roster loads the
  // row says nothing at all (there is nothing true to say yet), and when there is no pet the row leads to
  // the pet list instead of a toast: a toast «сначала выберите питомца» was read by people who had pets
  // but whose roster had not arrived yet, and it said nothing about where to go.
  const petRowText = (text: string) => (selectedPetId ? text : petsLoading ? ' ' : 'Сначала добавьте питомца');
  const petRow = (ready: () => void) =>
    selectedPetId
      ? { chevron: true, onClick: ready }
      : petsLoading
        ? {}
        : { chevron: true, onClick: () => navigate('/pets') };

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
            style={{ fontSize: 'var(--text-display)', margin: 0 }}
          >
            Настройки
          </h1>
        </div>

        <div className="safe-area-padding">
          {/* Order: what the app is for first (the pets, the reminders, the records), then how entering a record is set up, then
              the look of the app, the account, help, and the leaving and deleting at the very bottom. A pet's own settings (its
              look, its quick buttons, its defaults, its export) act on the pet that is selected in the switcher. */}

          <Group title="Питомцы" first>
            <SettingsRow
              icon={<PawPrint size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Мои питомцы"
              description="Добавить, изменить или удалить питомца"
              chevron
              onClick={() => navigate('/pets')}
            />
            <SettingsRow
              icon={<Palette size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Оформление питомца"
              description={
                getSelectedPet && getSelectedPet.current_user_is_owner === false
                  ? 'Меняет только владелец питомца'
                  : 'Образ, цвет, шрифт имени, рамка фото и фон ленты'
              }
              // Someone a pet is shared with sees the look but does not set it.
              {...(getSelectedPet && getSelectedPet.current_user_is_owner === false ? {} : { chevron: true, onClick: () => navigate('/pet-look') })}
            />
            <SettingsRow
              icon={<LayoutGrid size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="События питомца"
              description={
                getSelectedPet && getSelectedPet.current_user_is_owner === false
                  ? 'Меняет только владелец питомца'
                  : 'Какие записи предлагает «+» и в каком порядке'
              }
              {...(getSelectedPet && getSelectedPet.current_user_is_owner === false ? {} : { chevron: true, onClick: () => navigate('/pet-events') })}
            />
            {/* What a new form of this pet starts with: of everything on this screen, the only thing that is
                not the pet itself, but the pet's own values, so it sits with the pet. */}
            <SettingsRow
              icon={<SlidersHorizontal size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Значения по умолчанию"
              description="Что запомнено для выбранного питомца: поправить или забыть"
              chevron
              onClick={() => navigate('/form-defaults')}
            />
          </Group>

          {/* The medical card's own settings: what a vet asks (the profile of the selected pet) and the links given to a vet. */}
          <Group title="Медкарта">
            <SettingsRow
              icon={<HeartPulse size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Данные для врача"
              description={petRowText('Всё, что врач спросит о выбранном питомце')}
              {...petRow(() => navigate(`/pets/${selectedPetId}/medical-profile`))}
            />
            <SettingsRow
              icon={<Link2 size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Ссылки на медкарту"
              description="Общие ссылки на медкарты: открыть и отозвать может любой, у кого есть доступ к питомцу"
              chevron
              onClick={() => navigate('/settings/medical-links')}
            />
          </Group>

          {/* The row itself only ever shows a switch: the states where it cannot be turned on disable it and
              say, in the row, both why and what to do about it. On iPhone push works in an app added to the
              home screen, so plain Safari is not «браузер не поддерживает» (the same wording is in
              components/PushOffNotice.tsx). */}
          <Group title="Уведомления">
            <SettingsRow
              icon={<Bell size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Push-уведомления"
              description={
                pushState === 'unsupported'
                  ? needsHomeScreenForPush()
                    ? 'На iPhone напоминания работают, когда Petzy добавлен на экран «Домой». Добавьте его оттуда и включите напоминания здесь'
                    : 'Этот браузер не поддерживает push-уведомления. Напоминания о приёмах придут в другое приложение, если оно установлено'
                  : pushState === 'denied'
                    ? 'Заблокированы в настройках браузера. Разрешите уведомления для Petzy в настройках браузера или телефона'
                    : pushState === 'on'
                      ? 'Напоминания включены на этом устройстве: лекарства, прививки и обработки, документы, необычные показатели'
                      : 'Лекарства, прививки и обработки, документы, необычные показатели'
              }
              control={
                <Switch
                  aria-label="Push-уведомления"
                  checked={pushState === 'on'}
                  disabled={pushState === null || pushState === 'unsupported' || pushState === 'denied' || pushBusy}
                  onChange={handlePushToggle}
                />
              }
            />
          </Group>

          {/* The history screen is not a tab: this row and the card's «Вес» lead to it. */}
          <Group title="Записи">
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
              description={petRowText('Скачать записи питомца таблицей')}
              {...petRow(() => setExportVisible(true))}
            />
          </Group>

          {/* The types of record themselves: builtin ones can be relabelled and recoloured, custom ones made from scratch. They
              are the household's, not one pet's: they are added to a pet in «События питомца». */}
          <Group title="Новые записи">
            <SettingsRow
              icon={<Sparkles size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Типы событий"
              description="Свои типы записей со своими полями"
              chevron
              onClick={() => navigate('/event-types')}
            />
          </Group>

          <Group title="Внешний вид">
            <div style={{ padding: 'var(--spacing-md)', display: 'grid', gap: 'var(--spacing-sm)' }}>
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
              {/* The theme lives in this browser, not in the account: a person signed in on a second device
                  would otherwise look for the setting there and not find it. */}
              <div className="setting-row__description">Сохраняется на этом устройстве</div>
            </div>
          </Group>

          {/* The email is what a forgotten password is recovered with, so its state is on the row itself. */}
          <Group title="Аккаунт">
            <SettingsRow
              icon={<Mail size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Почта"
              description={accountText((a) =>
                a.pending_email
                  ? `${a.email_verified && a.email ? `Подтверждена: ${a.email} ` : ''}Ждёт подтверждения: ${a.pending_email}`
                  : a.email_verified
                    ? a.email
                    : 'Не указана. Нужна, чтобы восстановить пароль'
              )}
              chevron
              onClick={() => navigate('/settings/email')}
            />
            <SettingsRow
              icon={<KeyRound size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Пароль"
              description={accountText((a) => `Логин: ${a.username}`)}
              chevron
              onClick={() => navigate('/settings/password')}
            />
            {/* The profile is not only something you look at when someone else opens it: it is the answer to
                «кто я у человека, с которым делюсь питомцем». */}
            <SettingsRow
              icon={<UserRound size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Мой профиль"
              description="Как вас видят те, с кем вы делитесь питомцем"
              chevron
              onClick={() => navigate(`/users/${username}`)}
            />
          </Group>

          <Group title="О приложении">
            <SettingsRow
              icon={<CircleHelp size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Справка"
              description="Частые вопросы и как устроен каждый экран"
              chevron
              onClick={() => navigate('/help')}
            />
            <SettingsRow
              icon={<Compass size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Знакомство с Petzy"
              description="Показать вводные экраны ещё раз"
              chevron
              onClick={() => navigate('/welcome?replay=1')}
            />
            <SettingsRow
              icon={<ShieldCheck size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Политика конфиденциальности"
              description="Какие данные хранятся и где"
              chevron
              onClick={() => navigate('/privacy')}
            />
          </Group>

          {/* Admin: used to be its own bottom-tab entry shown only to admins, a whole tab-bar slot for one link. As a row here it
              needs no dedicated chrome and is reached like every other secondary screen. */}
          {isAdmin && (
            <Group title="Администрирование">
              <SettingsRow
                icon={<Users size={18} strokeWidth={2} style={{ display: 'block' }} />}
                label="Пользователи"
                description="Управление учётными записями"
                chevron
                onClick={() => navigate('/admin')}
              />
            </Group>
          )}

          {/* Leaving and deleting, apart from everything else and last: rare, and the second one cannot be undone. */}
          <Group title="Выход">
            <SettingsRow
              icon={<LogOut size={18} strokeWidth={2} style={{ display: 'block' }} />}
              label="Выйти из аккаунта"
              description="На этом устройстве"
              onClick={() => setLogoutDialogVisible(true)}
            />
            {!isAdmin ? (
              <SettingsRow
                icon={<Trash2 size={18} strokeWidth={2} style={{ display: 'block' }} />}
                label="Удалить аккаунт"
                description="Насовсем, вместе с данными"
                danger
                chevron
                onClick={() => navigate('/settings/delete-account')}
              />
            ) : (
              // The admin's account is never deletable, so the row is not hidden from them: it is shown without a
              // chevron, with the reason in place of what it would have said.
              <SettingsRow
                icon={<Trash2 size={18} strokeWidth={2} style={{ display: 'block' }} />}
                label="Удалить аккаунт"
                description="Учётную запись администратора удалить нельзя"
              />
            )}
          </Group>
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

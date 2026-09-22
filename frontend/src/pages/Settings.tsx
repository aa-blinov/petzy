import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dialog, Switch } from 'antd-mobile';
import { Moon, SlidersHorizontal, LayoutGrid, LogOut, PawPrint, Sparkles } from 'lucide-react';

import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../hooks/useAuth';
import { SettingsRow } from '../components/SettingsRow';

export function Settings() {
  const navigate = useNavigate();
  const { theme, setTheme, isDark } = useTheme();
  const { logout } = useAuth();
  const [logoutDialogVisible, setLogoutDialogVisible] = useState(false);

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
            {theme !== 'system' && (
              <SettingsRow
                icon={<SlidersHorizontal size={18} strokeWidth={2} style={{ display: 'block' }} />}
                label="Следовать за системой"
                description="Авто-переключение день/ночь"
                onClick={() => setTheme('system')}
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

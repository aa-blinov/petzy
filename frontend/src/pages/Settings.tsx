import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dialog, Switch } from 'antd-mobile';
import { Moon, SlidersHorizontal, LayoutGrid, LogOut } from 'lucide-react';

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
    await logout();
    navigate('/login');
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
            { key: 'cancel', text: 'Отмена', onClick: () => setLogoutDialogVisible(false) },
            { key: 'confirm', text: 'Выйти', bold: true, danger: true, onClick: confirmLogout },
          ],
        ]}
      />
    </div>
  );
}

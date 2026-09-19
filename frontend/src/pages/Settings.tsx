import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Dialog, Form, Switch } from 'antd-mobile';
import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../hooks/useAuth';

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
        <div className="safe-area-padding" style={{
          marginBottom: 'var(--spacing-lg)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          minHeight: '40px',
        }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Настройки</h2>
        </div>

        <div>
          <Form layout="horizontal" mode="card">
            <Form.Header>Внешний вид</Form.Header>
            <Form.Item
              extra={
                <Switch
                  checked={isDark}
                  onChange={(checked) => setTheme(checked ? 'dark' : 'light')}
                />
              }
              description={theme === 'system' ? 'Следует за настройками системы' : undefined}
            >
              Темная тема
            </Form.Item>
            {theme !== 'system' && (
              <Form.Item
                onClick={() => setTheme('system')}
                clickable
              >
                Использовать системную тему
              </Form.Item>
            )}

            <Form.Header>Значения по умолчанию</Form.Header>
            <Form.Item
              onClick={() => navigate('/form-defaults')}
              clickable
              arrow
            >
              Настройки форм
            </Form.Item>

            <Form.Header>Дашборд</Form.Header>
            <Form.Item
              onClick={() => navigate('/tiles-settings')}
              clickable
              arrow
            >
              Порядок тайлов
            </Form.Item>
          </Form>

          <Button
            block
            color="danger"
            fill="outline"
            style={{ marginTop: 'var(--spacing-lg)' }}
            onClick={() => setLogoutDialogVisible(true)}
          >
            Выйти из аккаунта
          </Button>
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

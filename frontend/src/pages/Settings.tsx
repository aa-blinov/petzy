import { useNavigate } from 'react-router-dom';
import { List, Switch } from 'antd-mobile';
import { useTheme } from '../hooks/useTheme';

export function Settings() {
  const navigate = useNavigate();
  const { theme, setTheme, isDark } = useTheme();

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Настройки</h2>
        </div>

        <div>
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <List header="Внешний вид" mode="card">
              <List.Item
                extra={
                  <Switch
                    checked={isDark}
                    onChange={(checked) => setTheme(checked ? 'dark' : 'light')}
                  />
                }
                description={theme === 'system' ? 'Следует за настройками системы' : undefined}
              >
                Темная тема
              </List.Item>
              {theme !== 'system' && (
                <List.Item
                  onClick={() => setTheme('system')}
                  clickable
                >
                  Использовать системную тему
                </List.Item>
              )}
            </List>

            <List header="Значения по умолчанию" mode="card">
              <List.Item
                onClick={() => navigate('/form-defaults')}
                clickable
                arrow
              >
                Настройки форм
              </List.Item>
            </List>
          </div>
        </div>
      </div>
    </div>
  );
}

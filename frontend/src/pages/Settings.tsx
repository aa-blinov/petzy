import { useNavigate } from 'react-router-dom';
import { List, Switch } from 'antd-mobile';
import { useTheme } from '../hooks/useTheme';

export function Settings() {
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();

  return (
    <div style={{ 
      minHeight: '100vh', 
      backgroundColor: 'var(--app-page-background)',
      paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
      paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
      color: 'var(--app-text-color)'
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ marginBottom: '16px', paddingLeft: 'max(16px, env(safe-area-inset-left))', paddingRight: 'max(16px, env(safe-area-inset-right))' }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: '24px', fontWeight: 600, margin: 0 }}>Настройки</h2>
        </div>
        
        {/* Theme Section */}
        <List header="Внешний вид" mode="card">
          <List.Item
            extra={
              <Switch
                checked={theme === 'dark'}
                onChange={(checked) => setTheme(checked ? 'dark' : 'light')}
              />
            }
          >
            Темная тема
          </List.Item>
        </List>

        {/* Management Section */}
        <List header="Управление" mode="card">
          <List.Item
            onClick={() => navigate('/pets')}
            clickable
            arrow
          >
            Мои питомцы
          </List.Item>
        </List>

        {/* Dashboard Section */}
        <List header="Дневник" mode="card">
          <List.Item
            onClick={() => navigate('/tiles-settings')}
            clickable
            arrow
          >
            Настройка тайлов
          </List.Item>
        </List>

        {/* Form Defaults Section */}
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
  );
}

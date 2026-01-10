import { useNavigate } from 'react-router-dom';
import { Form, Switch } from 'antd-mobile';
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
          </Form>
        </div>
      </div>
    </div>
  );
}

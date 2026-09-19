import { useNavigate, useLocation } from 'react-router-dom';
import { TabBar } from 'antd-mobile';
import { FileOutline, SetOutline, UserOutline, ClockCircleOutline, HeartOutline } from 'antd-mobile-icons';
import { useAdmin } from '../hooks/useAdmin';
import { hapticFeedback } from '../utils/haptic';

export function BottomTabBar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAdmin, isLoading } = useAdmin();

  const { pathname } = location;

  // Don't show on login page
  if (pathname === '/login') {
    return null;
  }

  const setRouteActive = (value: string) => {
    hapticFeedback('light');
    navigate(value);
  };

  const tabs = [
    {
      key: '/',
      title: 'Дневник',
      icon: <FileOutline />,
    },
    {
      key: '/medications',
      title: 'Лекарства',
      icon: <HeartOutline />,
    },
    {
      key: '/history',
      title: 'История',
      icon: <ClockCircleOutline />,
    },
    {
      key: '/settings',
      title: 'Настройки',
      icon: <SetOutline />,
    },
  ];

  // Only add admin tab after loading to prevent flickering
  if (!isLoading && isAdmin) {
    tabs.push({
      key: '/admin',
      title: 'Админ',
      icon: <UserOutline />,
    });
  }

  return (
    <div className="bottom-tab-bar-container">
      <div style={{
        height: '50px',
        display: 'flex',
        alignItems: 'center'
      }}>
        <TabBar
          activeKey={pathname}
          onChange={value => setRouteActive(value)}
          safeArea={false}
          style={{
            '--height': '50px',
            backgroundColor: 'transparent',
            width: '100%',
          } as React.CSSProperties}
        >
          {tabs.map(item => (
            <TabBar.Item
              key={item.key}
              // Wrap icon so we can give the active state a subtle
              // spring bounce instead of the default instant swap.
              icon={(active: boolean) => (
                <span
                  style={{
                    display: 'inline-flex',
                    transform: active ? 'scale(1.12)' : 'scale(1)',
                    transition: 'transform 280ms cubic-bezier(0.34, 1.56, 0.64, 1)',
                    color: active ? 'var(--app-primary-color)' : 'var(--app-text-secondary)',
                  }}
                >
                  {item.icon}
                </span>
              )}
              title={item.title}
            />
          ))}
        </TabBar>
      </div>
    </div>
  );
}


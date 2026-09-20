import { useNavigate, useLocation } from 'react-router-dom';
import { TabBar } from 'antd-mobile';
import { BookOpen, Pill, Clock, SlidersHorizontal, Users } from 'lucide-react';
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
      icon: <BookOpen size={22} strokeWidth={1.8} />,
    },
    {
      key: '/medications',
      title: 'Лекарства',
      icon: <Pill size={22} strokeWidth={1.8} />,
    },
    {
      key: '/history',
      title: 'История',
      icon: <Clock size={22} strokeWidth={1.8} />,
    },
    {
      key: '/settings',
      title: 'Настройки',
      icon: <SlidersHorizontal size={22} strokeWidth={1.8} />,
    },
  ];

  // Only add admin tab after loading to prevent flickering
  if (!isLoading && isAdmin) {
    tabs.push({
      key: '/admin',
      title: 'Админ',
      icon: <Users size={22} strokeWidth={1.8} />,
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
                    transition: `transform var(--motion-duration-fast) var(--motion-ease-emphasized)`,
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


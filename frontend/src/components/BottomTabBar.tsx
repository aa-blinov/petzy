import { useNavigate, useLocation } from 'react-router-dom';
import { TabBar } from 'antd-mobile';
import { AppOutline, SetOutline, UserOutline, ClockCircleOutline } from 'antd-mobile-icons';
import { useAdmin } from '../hooks/useAdmin';

export function BottomTabBar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAdmin } = useAdmin();

  const { pathname } = location;

  // Don't show on login page
  if (pathname === '/login') {
    return null;
  }

  const setRouteActive = (value: string) => {
    navigate(value);
  };

  const tabs = [
    {
      key: '/',
      title: 'Дашборд',
      icon: <AppOutline />,
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

  if (isAdmin) {
    tabs.push({
      key: '/admin',
      title: 'Админ',
      icon: <UserOutline />,
    });
  }

  return (
    <div style={{ 
      position: 'fixed', 
      bottom: 0, 
      left: 0, 
      right: 0, 
      backgroundColor: 'var(--app-card-background)', 
      borderTop: '1px solid var(--app-border-color)',
      paddingBottom: 'env(safe-area-inset-bottom)',
      zIndex: 1000,
    }}>
      <TabBar 
        activeKey={pathname} 
        onChange={value => setRouteActive(value)}
        style={{
          '--height': '50px',
        } as React.CSSProperties}
      >
        {tabs.map(item => (
          <TabBar.Item 
            key={item.key} 
            icon={item.icon} 
            title={item.title}
          />
        ))}
      </TabBar>
    </div>
  );
}


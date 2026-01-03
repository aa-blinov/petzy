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
              icon={item.icon} 
              title={item.title}
            />
          ))}
        </TabBar>
      </div>
    </div>
  );
}


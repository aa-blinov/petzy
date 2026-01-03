import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { NavBar, Button, Dropdown } from 'antd-mobile';
import { useAuth } from '../hooks/useAuth';
import { usePet } from '../hooks/usePet';

export function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { selectedPetName, selectPet, pets, selectedPetId } = usePet();
  const [dropdownActiveKey, setDropdownActiveKey] = useState<string | null>(null);

  const handleLogout = async () => {
    await logout();
  };

  const handlePetSelect = (petId: string) => {
    const pet = pets.find(p => p._id === petId);
    if (pet) {
      selectPet(pet);
      // Добавляем небольшую задержку для плавной анимации закрытия
      setTimeout(() => {
        setDropdownActiveKey(null);
      }, 250);
    }
  };

  const handleBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate('/');
    }
  };

  // Don't show navbar on login page
  if (location.pathname === '/login') {
    return null;
  }

  // Show back button only on pages that are not main tabs
  const isMainTab = ['/', '/settings', '/admin', '/history'].includes(location.pathname) || location.pathname === '';

  const logo = (
    <img
      src="/logo.svg"
      alt="Petzy"
      style={{ width: '44px', height: '44px', display: 'inline-block', verticalAlign: 'middle' }}
    />
  );

  // На главной странице - только логотип, на других - используем встроенную кнопку назад + логотип
  const leftContent = (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-start' }}>
      {logo}
    </div>
  );

  const rightContent = (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'flex-end', width: '100%' }}>
      {pets.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', height: '100%', fontSize: '14px' }}>
          <Dropdown
            activeKey={dropdownActiveKey}
            onChange={(key) => setDropdownActiveKey(key)}
            style={{
              '--adm-font-size-main': '14px',
            } as React.CSSProperties}
          >
            <Dropdown.Item
              key="pets"
              title={<span style={{ fontSize: '14px' }}>{selectedPetName || 'Выбрать...'}</span>}
              arrow
              style={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                fontSize: '14px',
                '--adm-font-size-main': '14px',
              } as React.CSSProperties}
            >
              <div style={{ padding: '8px 0' }}>
                {pets.map(pet => (
                  <div
                    key={pet._id}
                    onClick={() => handlePetSelect(pet._id)}
                    style={{
                      padding: '12px 16px',
                      cursor: 'pointer',
                      backgroundColor: selectedPetId === pet._id ? 'var(--adm-color-primary-light)' : 'transparent',
                      borderBottom: '1px solid var(--app-border-color)',
                    }}
                  >
                    {pet.name}
                  </div>
                ))}
              </div>
            </Dropdown.Item>
          </Dropdown>
        </div>
      )}
      <Button
        fill="none"
        size="small"
        onClick={handleLogout}
        style={{ padding: '8px', minWidth: '44px' }}
      >
        Выйти
      </Button>
    </div>
  );

  return (
    <>
      <NavBar
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 1000,
          paddingTop: 'env(safe-area-inset-top)',
          backgroundColor: 'var(--app-card-background)',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        }}
        back={isMainTab ? null : true}
        onBack={handleBack}
        left={leftContent}
        right={rightContent}
      />
    </>
  );
}


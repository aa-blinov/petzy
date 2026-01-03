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
      style={{ 
        width: '38px', 
        height: '38px', 
        display: 'block',
      }}
    />
  );

  // На главной странице - только логотип, на других - используем встроенную кнопку назад + логотип
  const leftContent = (
    <div style={{ display: 'flex', alignItems: 'center', height: '100%' }}>
      {logo}
    </div>
  );

  const rightContent = (
    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'flex-end', height: '100%' }}>
      {pets.length > 0 && (
        <Dropdown
          activeKey={dropdownActiveKey}
          onChange={(key) => setDropdownActiveKey(key)}
          style={{
            '--adm-font-size-main': '14px',
          } as React.CSSProperties}
        >
          <Dropdown.Item
            key="pets"
            title={
              <div style={{ 
                fontSize: '14px', 
                padding: '4px 8px', 
                borderRadius: '16px', 
                backgroundColor: 'var(--app-page-background)',
                border: '1px solid var(--app-border-color)',
                display: 'flex',
                alignItems: 'center',
                color: 'var(--app-text-color)'
              }}>
                {selectedPetName || 'Выбрать'}
              </div>
            }
            arrow
          >
            <div style={{ padding: '8px 0', backgroundColor: 'var(--app-card-background)' }}>
              {pets.map(pet => (
                <div
                  key={pet._id}
                  onClick={() => handlePetSelect(pet._id)}
                  style={{
                    padding: '12px 20px',
                    cursor: 'pointer',
                    fontSize: '16px',
                    backgroundColor: selectedPetId === pet._id ? 'var(--adm-color-primary-light)' : 'transparent',
                    borderBottom: '1px solid var(--app-border-color)',
                    color: 'var(--app-text-color)'
                  }}
                >
                  {pet.name}
                </div>
              ))}
            </div>
          </Dropdown.Item>
        </Dropdown>
      )}
      <Button
        fill="none"
        size="small"
        onClick={handleLogout}
        style={{ 
          padding: '4px 8px', 
          color: 'var(--app-text-secondary)',
          fontSize: '14px'
        }}
      >
        Выйти
      </Button>
    </div>
  );

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      zIndex: 1000,
      backgroundColor: 'var(--app-card-background)',
      paddingTop: 'env(safe-area-inset-top)',
      boxShadow: '0 1px 10px rgba(0, 0, 0, 0.2)',
    }}>
      <NavBar
        style={{
          '--height': '64px',
          borderBottom: 'none',
        } as React.CSSProperties}
        back={isMainTab ? null : true}
        onBack={handleBack}
        left={leftContent}
        right={rightContent}
      />
    </div>
  );
}


import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { NavBar, Button, Picker } from 'antd-mobile';
import { useAuth } from '../hooks/useAuth';
import { usePet } from '../hooks/usePet';

export function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { selectedPetName, selectPet, pets, selectedPetId } = usePet();
  const [pickerVisible, setPickerVisible] = useState(false);

  const handleLogout = async () => {
    await logout();
  };

  const handlePetSelect = (value: (string | number | null)[]) => {
    const petId = value[0] as string;
    if (!petId) return;
    const pet = pets.find(p => p._id === petId);
    if (pet) {
      selectPet(pet);
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
  const isMainTab = ['/', '/settings', '/admin', '/history'].includes(location.pathname) || 
                    location.pathname === '' ||
                    location.pathname.startsWith('/medications');

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
        <>
          <Button
            fill="none"
            size="small"
            onClick={() => setPickerVisible(true)}
            style={{ 
              padding: '4px 8px',
              fontSize: '14px',
              borderRadius: '16px', 
              backgroundColor: 'var(--app-page-background)',
              border: '1px solid var(--app-border-color)',
              color: 'var(--app-text-color)'
            }}
          >
            {selectedPetName || 'Выбрать'}
          </Button>
          <Picker
            columns={[pets.map(pet => ({ label: pet.name, value: pet._id }))]}
            visible={pickerVisible}
            onClose={() => setPickerVisible(false)}
            value={selectedPetId ? [selectedPetId] : []}
            onConfirm={(val) => {
              handlePetSelect(val);
              setPickerVisible(false);
            }}
            cancelText="Отмена"
            confirmText="Выбрать"
          />
        </>
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


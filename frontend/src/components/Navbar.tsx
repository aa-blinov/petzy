import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { NavBar, Button, Popup } from 'antd-mobile';
import { useAuth } from '../hooks/useAuth';
import { usePet } from '../hooks/usePet';
import { CheckOutline, DownOutline } from 'antd-mobile-icons';
import { hapticFeedback } from '../utils/haptic';
import { PetImage } from './PetImage';

export function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { selectedPetName, selectPet, pets, selectedPetId } = usePet();
  const [pickerVisible, setPickerVisible] = useState(false);
  const [pendingNavigate, setPendingNavigate] = useState<string | null>(null);

  const handleLogout = async () => {
    hapticFeedback('medium');
    await logout();
  };

  const handlePetSelect = (pet: any) => {
    hapticFeedback('light');
    selectPet(pet);
    setPickerVisible(false);
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
  const mainTabs = ['/', '/medications', '/settings', '/admin', '/history'];
  const isMainTab = mainTabs.includes(location.pathname) || location.pathname === '';

  const logo = (
    <div
      style={{
        fontFamily: 'var(--app-font-bubble)',
        fontSize: '28px',
        fontWeight: 700,
        background: 'var(--app-brand-gradient)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        letterSpacing: '-0.5px',
        display: 'flex',
        alignItems: 'center',
        filter: 'drop-shadow(var(--app-shadow-light))'
      }}
    >
      Petzy
    </div>
  );

  // На главной странице - только логотип, на других - используем встроенную кнопку назад + логотип
  const leftContent = (
    <div style={{ display: 'flex', alignItems: 'center', height: '100%' }}>
      {logo}
    </div>
  );

  const rightContent = (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'flex-end', height: '100%' }}>
      {pets.length > 0 && (
        <>
          <div
            className="tap-feedback"
            onClick={() => {
              hapticFeedback('light');
              setPickerVisible(true);
            }}
            style={{
              height: '36px',
              padding: '0 12px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer',
              borderRadius: '24px',
              backgroundColor: 'var(--app-page-background)',
              border: '1px solid var(--app-border-color)',
              transition: 'all 0.2s ease',
              boxShadow: 'inset 0 1px 2px var(--app-white-05), var(--app-shadow-light)',
            }}
          >
            <span style={{ fontSize: '15px', fontWeight: 600, color: 'var(--app-text-color)' }}>
              {selectedPetName}
            </span>
            <DownOutline style={{ fontSize: '10px', color: 'var(--app-text-secondary)' }} />
          </div>

          <Popup
            visible={pickerVisible}
            onMaskClick={() => setPickerVisible(false)}
            onClose={() => setPickerVisible(false)}
            afterClose={() => {
              if (pendingNavigate) {
                navigate(pendingNavigate);
                setPendingNavigate(null);
              }
            }}
            bodyStyle={{
              borderTopLeftRadius: '16px',
              borderTopRightRadius: '16px',
              minHeight: '30vh',
              backgroundColor: 'var(--app-page-background)',
            }}
          >
            <div style={{ padding: '20px' }}>
              <div style={{
                fontSize: '18px',
                fontWeight: 600,
                marginBottom: '20px',
                textAlign: 'center',
                color: 'var(--app-text-color)'
              }}>
                Выбрать питомца
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {pets.map(pet => (
                  <div
                    key={pet._id}
                    className="tap-feedback active-dim"
                    onClick={() => handlePetSelect(pet)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '12px 16px',
                      backgroundColor: 'var(--app-card-background)',
                      borderRadius: '12px',
                      cursor: 'pointer',
                      border: pet._id === selectedPetId ? '2px solid var(--app-primary-color)' : '1px solid var(--app-border-color)',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      {pet.photo_url ? (
                        <PetImage
                          src={pet.photo_url}
                          alt={pet.name}
                          size={40}
                          style={{ borderRadius: '50%' }}
                        />
                      ) : (
                        <div style={{
                          width: '40px',
                          height: '40px',
                          borderRadius: '50%',
                          backgroundColor: 'var(--adm-color-border)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '20px'
                        }}>
                          🐱
                        </div>
                      )}
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '16px', fontWeight: 600, color: 'var(--app-text-color)' }}>{pet.name}</span>
                        <span style={{ fontSize: '12px', color: 'var(--app-text-secondary)' }}>{pet.breed || pet.species || 'Питомец'}</span>
                      </div>
                    </div>
                    {pet._id === selectedPetId && (
                      <CheckOutline style={{ fontSize: '20px', color: 'var(--adm-color-primary)' }} />
                    )}
                  </div>
                ))}
                <Button
                  block
                  fill="none"
                  color="primary"
                  onClick={() => {
                    hapticFeedback('light');
                    setPickerVisible(false);
                    setPendingNavigate('/pets');
                  }}
                  style={{ marginTop: '8px', fontSize: '15px' }}
                >
                  Управление питомцами
                </Button>
              </div>
            </div>
          </Popup>
        </>
      )}
      <div
        className="tap-feedback"
        onClick={handleLogout}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '36px',
          height: '36px',
          borderRadius: '50%',
          cursor: 'pointer',
          backgroundColor: 'var(--app-white-05)',
          color: 'var(--app-text-secondary)',
          transition: 'all 0.2s ease',
          border: '1px solid var(--app-white-10)'
        }}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
          <polyline points="16 17 21 12 16 7"></polyline>
          <line x1="21" y1="12" x2="9" y2="12"></line>
        </svg>
      </div>
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
      paddingTop: 'var(--safe-area-top)',
      boxShadow: 'var(--app-shadow)',
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


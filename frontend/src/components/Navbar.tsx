import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { NavBar, Button, Popup } from 'antd-mobile';
import { usePet } from '../hooks/usePet';
import { CheckOutline, DownOutline } from 'antd-mobile-icons';
import { hapticFeedback } from '../utils/haptic';
import { PetImage } from './PetImage';
import { speciesIcon } from '../utils/speciesIcon';

export function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { selectedPetName, selectPet, pets, selectedPetId } = usePet();
  const [pickerVisible, setPickerVisible] = useState(false);
  const [pendingNavigate, setPendingNavigate] = useState<string | null>(null);

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
  const leftContent = isMainTab ? (
    <div style={{ display: 'flex', alignItems: 'center', height: '100%' }}>
      {logo}
    </div>
  ) : null;

  const rightContent = (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'flex-end', height: '100%' }}>
      {pets.length === 1 && (
        // Single-pet households: show the name as a plain label. No
        // chevron, no tap target — there's nothing to switch to. Keeps
        // the navbar quiet for the most common starter state.
        <span
          aria-label={`Текущий питомец: ${selectedPetName}`}
          style={{
            height: '36px',
            padding: '0 12px',
            display: 'flex',
            alignItems: 'center',
            color: 'var(--app-text-color)',
            fontSize: '15px',
            fontWeight: 600,
          }}
        >
          {selectedPetName}
        </span>
      )}
      {pets.length >= 2 && (
        <>
          <button
            type="button"
            className="tap-feedback"
            onClick={() => {
              hapticFeedback('light');
              setPickerVisible(true);
            }}
            aria-label="Сменить питомца"
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
              color: 'inherit',
              font: 'inherit',
            }}
          >
            <span style={{ fontSize: '15px', fontWeight: 600, color: 'var(--app-text-color)' }}>
              {selectedPetName}
            </span>
            <DownOutline style={{ fontSize: '10px', color: 'var(--app-text-secondary)' }} />
          </button>

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
                  <button
                    type="button"
                    key={pet._id}
                    className="tap-feedback active-dim"
                    onClick={() => handlePetSelect(pet)}
                    aria-label={`Выбрать питомца ${pet.name}`}
                    aria-pressed={pet._id === selectedPetId}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '12px 16px',
                      backgroundColor: 'var(--app-card-background)',
                      borderRadius: '12px',
                      cursor: 'pointer',
                      border: pet._id === selectedPetId ? '2px solid var(--app-primary-color)' : '1px solid var(--app-border-color)',
                      transition: 'all 0.2s ease',
                      color: 'inherit',
                      font: 'inherit',
                      textAlign: 'left',
                      width: '100%',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      {pet.photo_url ? (
                        <PetImage
                          src={pet.photo_url}
                          alt={pet.name}
                          size={40}
                          species={pet.species}
                          style={{ borderRadius: '50%' }}
                        />
                      ) : (
                        <div style={{
                          width: '40px',
                          height: '40px',
                          borderRadius: '50%',
                          backgroundColor: 'var(--app-accent-soft)',
                          color: 'var(--app-accent-deep)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}>
                          {(() => {
                            const Icon = speciesIcon(pet.species);
                            return <Icon size={22} strokeWidth={1.8} aria-hidden />;
                          })()}
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
                  </button>
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
          paddingLeft: 0,
          paddingRight: 0,
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


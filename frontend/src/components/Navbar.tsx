import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button, Popup } from 'antd-mobile';
import { usePet } from '../hooks/usePet';
import { CheckOutline, DownOutline, LeftOutline } from 'antd-mobile-icons';
import { hapticFeedback } from '../utils/haptic';
import { PetImage } from './PetImage';
import { speciesIcon } from '../utils/speciesIcon';
import type { Pet } from '../services/pets.service';
import { SPECIES_LABELS } from '../utils/constants';
import { MAIN_TAB_PATHS } from '../utils/navigation';

export function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { selectedPetName, selectPet, pets, selectedPetId } = usePet();
  const [pickerVisible, setPickerVisible] = useState(false);
  const [pendingNavigate, setPendingNavigate] = useState<string | null>(null);

  const handlePetSelect = (pet: Pet) => {
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

  // Login and onboarding own the whole viewport
  if (location.pathname === '/login' || location.pathname === '/welcome') {
    return null;
  }

  // Show back button only on pages that are not main tabs
  const isMainTab = MAIN_TAB_PATHS.includes(location.pathname) || location.pathname === '';

  // The pet switcher only belongs on screens whose content is scoped to
  // one pet, or on the other main tabs for a consistent topbar — not on
  // secondary/form screens: in the admin panel it controls nothing, and
  // inside a form it silently repointed the record being edited at a
  // different animal. Settings has both reasons to carry it: it's a main
  // tab like the others, and one of its own rows (dashboard tile order)
  // is itself per-pet.
  const showPetSwitcher = isMainTab;

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

  // Main tabs show the logo; every other screen gets a back button.
  const leftContent = isMainTab ? (
    logo
  ) : (
    <button type="button" className="app-navbar__back" aria-label="Назад" onClick={handleBack}>
      <LeftOutline aria-hidden />
    </button>
  );

  const rightContent = !showPetSwitcher ? null : (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'flex-end', height: '100%', minWidth: 0, maxWidth: '100%' }}>
      {/* Single-pet households get nothing here. The name already sits
          on the pet card right below, so a label in the navbar was a
          duplicate of it — and with nothing to switch to, a selector
          would be dead weight. The picker appears from the second pet
          onwards, where the name finally carries information. */}
      {pets.length >= 2 && (
        <>
          <button
            type="button"
            className="tap-feedback touch-target"
            onClick={() => {
              hapticFeedback('light');
              setPickerVisible(true);
            }}
            aria-label={`${selectedPetName}, сменить питомца`}
            style={{
              height: '36px',
              // A long name ("Сэр Бартоломью Пушистый Третий…") pushed the
              // logo off-screen and clipped from the left; cap the chip.
              maxWidth: '100%',
              minWidth: 0,
              padding: '0 12px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--app-page-background)',
              border: '1px solid var(--app-border-color)',
              transition: 'border-color var(--motion-duration-fast) var(--motion-ease-standard), background-color var(--motion-duration-fast) var(--motion-ease-standard)',
              boxShadow: 'inset 0 1px 2px var(--app-white-05), var(--app-shadow-light)',
              color: 'inherit',
              font: 'inherit',
            }}
          >
            <span
              style={{
                fontSize: '15px',
                fontWeight: 600,
                color: 'var(--app-text-color)',
                minWidth: 0,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {selectedPetName}
            </span>
            <DownOutline aria-hidden style={{ fontSize: '10px', color: 'var(--app-text-secondary)', flexShrink: 0 }} />
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
                      transition: 'border-color var(--motion-duration-fast) var(--motion-ease-standard), background-color var(--motion-duration-fast) var(--motion-ease-standard)',
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
                          style={{ borderRadius: 'var(--radius-md)' }}
                        />
                      ) : (
                        <div style={{
                          width: '40px',
                          height: '40px',
                          borderRadius: 'var(--radius-md)',
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
                        <span style={{ fontSize: '12px', color: 'var(--app-text-secondary)' }}>{pet.breed || (pet.species && SPECIES_LABELS[pet.species]) || 'Питомец'}</span>
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
    <header style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      zIndex: 1000,
      backgroundColor: 'var(--app-card-background)',
      paddingTop: 'var(--safe-area-top)',
      boxShadow: 'var(--app-shadow)',
    }}>
      <div className="app-navbar">
        <div className="app-navbar__left">{leftContent}</div>
        <div className="app-navbar__right">{rightContent}</div>
      </div>
    </header>
  );
}


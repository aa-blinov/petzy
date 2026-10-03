import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { petsService, type Pet } from '../services/pets.service';
import { usePet } from '../hooks/usePet';
import { NoPetState } from '../components/NoPetState';
import { PetSummaryCard } from '../components/PetSummaryCard';
import { SpinnerButton } from '../components/SpinnerButton';
import { PET_ACCENTS, PET_TAGLINE_MAX, petLookOf, type PetLook } from '../utils/petLook';
import { showToast } from '../utils/toast';

const BRAND = { key: '', label: 'Терракот', swatch: '#C46A3F' };

/** «Карточка питомца»: a line under the name and a colour, for the selected pet. They are how the family sees the pet,
 *  so everyone with access to it sees (and may change) the same. */
export function PetLookSettings() {
  const { getSelectedPet } = usePet();
  if (!getSelectedPet) return <NoPetState what="Карточка питомца" />;
  // Keyed by the pet: choosing another pet in the switcher opens that pet's own card.
  return <PetLookFor key={getSelectedPet._id} pet={getSelectedPet} />;
}

function PetLookFor({ pet }: { pet: Pet }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const saved = petLookOf(pet);
  const [tagline, setTagline] = useState(saved.tagline ?? '');
  const [accent, setAccent] = useState(saved.accent ?? '');
  const [saving, setSaving] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const draft: PetLook = { tagline: tagline.trim(), accent };

  const save = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const look = await petsService.saveLook(pet._id, draft);
      queryClient.setQueryData<Pet[]>(['pets'], (pets) => pets?.map((p) => (p._id === pet._id ? { ...p, look } : p)));
      showToast.success('Карточка сохранена');
      navigate('/settings');
    } catch {
      showToast.failure('Не удалось сохранить карточку');
    } finally {
      if (mountedRef.current) setSaving(false);
    }
  };

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Карточка питомца</h1>
          <p style={{ margin: 'var(--spacing-sm) 0 0', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
            Питомец: {pet.name}. Подпись и цвет видят все, у кого есть доступ к питомцу, и каждый из них может их поменять
          </p>
        </div>

        <div style={{ padding: '0 var(--spacing-md)' }}>
          <PetSummaryCard pet={pet} look={draft} />

          <div className="card-soft" style={{ padding: '16px', marginBottom: 'var(--spacing-md)' }}>
            <label htmlFor="pet-tagline" style={{ display: 'block', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-text-primary)', marginBottom: '8px' }}>
              Подпись
            </label>
            <input
              id="pet-tagline"
              value={tagline}
              maxLength={PET_TAGLINE_MAX}
              onChange={(e) => setTagline(e.target.value)}
              enterKeyHint="done"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void save();
                }
              }}
              placeholder="Например, хозяин дивана"
              autoComplete="off"
              style={{
                width: '100%',
                boxSizing: 'border-box',
                minHeight: 'var(--touch-min)',
                padding: '0 12px',
                border: '1px solid var(--app-border-color)',
                borderRadius: 'var(--radius-md)',
                background: 'var(--app-page-background)',
                color: 'var(--app-text-primary)',
                fontSize: 'var(--text-md)',
                fontFamily: 'inherit',
              }}
            />
            <div style={{ marginTop: '6px', fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)', textAlign: 'right' }}>
              {tagline.length} из {PET_TAGLINE_MAX}
            </div>

            <div id="pet-accent-label" style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-text-primary)', margin: '8px 0' }}>
              Цвет
            </div>
            <div role="radiogroup" aria-labelledby="pet-accent-label" style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
              {[BRAND, ...PET_ACCENTS].map((a) => {
                const on = accent === a.key;
                return (
                  <button
                    key={a.key || 'brand'}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    aria-label={a.label}
                    title={a.label}
                    className="tap-feedback"
                    onClick={() => setAccent(a.key)}
                    style={{
                      width: 'var(--touch-min)',
                      height: 'var(--touch-min)',
                      borderRadius: '50%',
                      border: on ? '3px solid var(--app-text-primary)' : '3px solid transparent',
                      boxShadow: on ? 'inset 0 0 0 2px var(--app-card-background)' : 'none',
                      background: a.swatch,
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: 0,
                      cursor: 'pointer',
                    }}
                  >
                    {on && <Check size={20} strokeWidth={3} aria-hidden />}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ paddingBottom: 'var(--spacing-md)' }}>
            <SpinnerButton type="button" block loading={saving} onClick={save}>
              Сохранить
            </SpinnerButton>
          </div>
        </div>
      </div>
    </div>
  );
}

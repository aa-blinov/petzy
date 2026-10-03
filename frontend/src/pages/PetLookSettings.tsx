import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { petsService, type Pet } from '../services/pets.service';
import { usePet } from '../hooks/usePet';
import { NoPetState } from '../components/NoPetState';
import { PetImage } from '../components/PetImage';
import { getSpecies } from '../utils/species';
import { PetSummaryCard } from '../components/PetSummaryCard';
import { SpinnerButton } from '../components/SpinnerButton';
import { PET_ACCENTS, PET_FONTS, PET_FRAMES, PET_TAGLINE_MAX, loadPetFont, petFontStyle, petFrameStyle, petLookOf, type PetLook } from '../utils/petLook';
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
  const [font, setFont] = useState(saved.font ?? '');
  const [frame, setFrame] = useState(saved.frame ?? '');
  const SpeciesIcon = getSpecies(pet.species).icon;
  const [saving, setSaving] = useState(false);
  const mountedRef = useRef(true);

  // The options show the name in each face, so all of them are fetched here (and only here).
  useEffect(() => {
    PET_FONTS.forEach((f) => void loadPetFont(f));
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const draft: PetLook = { tagline: tagline.trim(), accent, font, frame };

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

            <div id="pet-font-label" style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-text-primary)', margin: '16px 0 8px' }}>
              Шрифт имени
            </div>
            <div role="radiogroup" aria-labelledby="pet-font-label" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '8px' }}>
              {[{ key: '', label: 'Обычный', family: '', weight: 700, scale: 1 }, ...PET_FONTS].map((f) => {
                const on = font === f.key;
                const face = PET_FONTS.find((x) => x.key === f.key);
                return (
                  <button
                    key={f.key || 'plain'}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    aria-label={`${pet.name}, ${f.label}`}
                    className="tap-feedback"
                    onClick={() => setFont(f.key)}
                    style={{
                      minHeight: 'var(--touch-min)',
                      padding: '6px 12px',
                      borderRadius: 'var(--radius-md)',
                      border: on ? '2px solid var(--app-accent-deep)' : '1px solid var(--app-border-color)',
                      background: on ? 'var(--app-accent-soft)' : 'var(--app-page-background)',
                      color: 'var(--app-text-primary)',
                      fontFamily: 'inherit',
                      fontSize: 'var(--text-lg)',
                      fontWeight: 700,
                      textAlign: 'center',
                      cursor: 'pointer',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      ...petFontStyle(face, 'var(--text-lg)'),
                    }}
                  >
                    {pet.name}
                  </button>
                );
              })}
            </div>

            <div id="pet-frame-label" style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-text-primary)', margin: '16px 0 8px' }}>
              Рамка фото
            </div>
            <div role="radiogroup" aria-labelledby="pet-frame-label" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '8px' }}>
              {[{ key: '', label: 'Без рамки' }, ...PET_FRAMES].map((f) => {
                const on = frame === f.key;
                const sample = petFrameStyle(f.key, 0.45);
                return (
                  <button
                    key={f.key || 'plain'}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    className="tap-feedback"
                    onClick={() => setFrame(f.key)}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '8px',
                      minHeight: 'var(--touch-min)',
                      padding: '12px 4px 8px',
                      borderRadius: 'var(--radius-md)',
                      border: on ? '2px solid var(--app-accent-deep)' : '1px solid var(--app-border-color)',
                      background: on ? 'var(--app-accent-soft)' : 'var(--app-page-background)',
                      color: 'var(--app-text-primary)',
                      fontFamily: 'inherit',
                      fontSize: 'var(--text-xs)',
                      cursor: 'pointer',
                    }}
                  >
                    <span
                      aria-hidden
                      style={{
                        width: '44px',
                        height: '44px',
                        overflow: 'hidden',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--app-accent-soft)',
                        color: 'var(--app-accent-deep)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        ...sample.box,
                      }}
                    >
                      {pet.photo_url ? (
                        <PetImage src={pet.photo_url} alt="" size={44} species={pet.species} style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 0, ...sample.image }} />
                      ) : (
                        <SpeciesIcon size={24} strokeWidth={1.6} aria-hidden />
                      )}
                    </span>
                    {f.label}
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

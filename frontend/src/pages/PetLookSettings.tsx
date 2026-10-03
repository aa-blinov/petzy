import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { petsService, type Pet } from '../services/pets.service';
import { usePet } from '../hooks/usePet';
import { NoPetState } from '../components/NoPetState';
import { PetPhotoFill } from '../components/PetPhotoFill';
import { FrameCropModal } from '../components/FrameCropModal';
import { PetSummaryCard } from '../components/PetSummaryCard';
import { SpinnerButton } from '../components/SpinnerButton';
import { getSpecies } from '../utils/species';
import {
  PET_ACCENTS,
  PET_BACKDROPS,
  PET_FONTS,
  PET_FRAMES,
  PET_FRAME_GROUPS,
  PET_SCENES,
  PET_TAGLINE_MAX,
  PET_VIBES,
  loadPetFont,
  petAccentAttr,
  petBackdropKey,
  petBackdropStyle,
  petFontStyle,
  petFrameStyle,
  petLookOf,
  petSceneStyle,
  petTintAttr,
  petTintHex,
  type PetCrop,
  type PetLook,
} from '../utils/petLook';
import { showToast } from '../utils/toast';

const BRAND = { key: '', label: 'Терракот', swatch: '#C46A3F' };

const labelStyle: CSSProperties = { fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-text-primary)', margin: '16px 0 8px' };
const optionBase: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '8px',
  minHeight: 'var(--touch-min)',
  padding: '12px 4px 8px',
  borderRadius: 'var(--radius-md)',
  color: 'var(--app-text-primary)',
  fontFamily: 'inherit',
  fontSize: 'var(--text-xs)',
  cursor: 'pointer',
};
const optionState = (on: boolean): CSSProperties => ({
  border: on ? '2px solid var(--app-accent-deep)' : '1px solid var(--app-border-color)',
  background: on ? 'var(--app-accent-soft)' : 'var(--app-page-background)',
});

/** «Оформление питомца»: how the pet shows in the feed, for the selected pet. It is how the family sees the pet, so everyone
 *  with access to it sees (and may change) the same. */
export function PetLookSettings() {
  const { getSelectedPet } = usePet();
  if (!getSelectedPet) return <NoPetState what="Оформление питомца" />;
  // Keyed by the pet: choosing another pet in the switcher opens that pet's own card.
  return <PetLookFor key={getSelectedPet._id} pet={getSelectedPet} />;
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="card-soft" style={{ padding: '16px', marginBottom: 'var(--spacing-md)' }}>
      <h2 style={{ margin: 0, fontSize: 'var(--text-md)', fontWeight: 700, color: 'var(--app-text-primary)' }}>{title}</h2>
      {children}
    </section>
  );
}

/** A row of round colour buttons: one radio group, `none` first (the pet's own colour, or the brand's). */
function Swatches({ label, value, onChange, noneLabel }: { label: string; value: string; onChange: (key: string) => void; noneLabel: string }) {
  const id = `sw-${label}`;
  return (
    <>
      <div id={id} style={labelStyle}>
        {label}
      </div>
      <div role="radiogroup" aria-labelledby={id} style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
        {[{ ...BRAND, label: noneLabel }, ...PET_ACCENTS].map((a) => {
          const on = value === a.key;
          return (
            <button
              key={a.key || 'none'}
              type="button"
              role="radio"
              aria-checked={on}
              aria-label={a.label}
              title={a.label}
              className="tap-feedback"
              onClick={() => onChange(a.key)}
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
    </>
  );
}

/** A grid of backdrops, each drawn as a small sample of itself in the chosen tint. */
function BackdropGrid({
  label,
  items,
  value,
  onChange,
  hex,
  photoUrl,
  tintAttr,
}: {
  label: string;
  items: readonly { key: string; label: string }[];
  value: string;
  onChange: (key: string) => void;
  hex: string;
  photoUrl?: string;
  tintAttr: { 'data-pet-tint'?: string };
}) {
  const id = `bd-${label}`;
  return (
    <>
      <div id={id} style={labelStyle}>
        {label}
      </div>
      <div role="radiogroup" aria-labelledby={id} style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '8px' }}>
        {items.map((b) => {
          const on = value === b.key;
          return (
            <button key={b.key} type="button" role="radio" aria-checked={on} className="tap-feedback" onClick={() => onChange(b.key)} style={{ ...optionBase, ...optionState(on) }}>
              <span
                aria-hidden
                {...tintAttr}
                style={{
                  position: 'relative',
                  width: '100%',
                  height: '40px',
                  overflow: 'hidden',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--app-border-color)',
                  background: 'var(--app-card-background)',
                  ...petBackdropStyle(b.key, hex),
                }}
              >
                {b.key === 'photo' && photoUrl && (
                  <span style={{ position: 'absolute', inset: 0, backgroundImage: `url(${photoUrl})`, backgroundSize: 'cover', filter: 'blur(8px) saturate(1.3)', transform: 'scale(1.5)', opacity: 0.7 }} />
                )}
              </span>
              {b.label}
            </button>
          );
        })}
      </div>
    </>
  );
}

function PetLookFor({ pet }: { pet: Pet }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const saved = petLookOf(pet);
  const [tagline, setTagline] = useState(saved.tagline ?? '');
  const [accent, setAccent] = useState(saved.accent ?? '');
  const [font, setFont] = useState(saved.font ?? '');
  const [frame, setFrame] = useState(saved.frame ?? '');
  const [crops, setCrops] = useState<Record<string, PetCrop>>(saved.crops ?? {});
  // Empty keeps the default (a tint of the pet's colour, none without one); the grid shows what that comes to.
  const [backdrop, setBackdrop] = useState(saved.backdrop ?? '');
  const [tint, setTint] = useState(saved.tint ?? '');
  const [scene, setScene] = useState(saved.scene ?? '');
  // The frame being cropped, from the button under the frames: each frame has a window of its own shape and its own crop.
  const [cropping, setCropping] = useState<string | null>(null);
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

  const draft: PetLook = { tagline: tagline.trim(), accent, font, frame, crops, backdrop, tint, scene };
  const hex = petTintHex(draft);
  const tintAttr = petTintAttr(draft);

  const applyVibe = (v: (typeof PET_VIBES)[number]) => {
    setAccent(v.look.accent);
    setFont(v.look.font);
    setBackdrop(v.look.backdrop);
    setTint(v.look.tint);
    setScene(v.look.scene);
    setFrame(v.look.frame);
  };

  const reset = () => {
    setAccent('');
    setFont('');
    setFrame('');
    setBackdrop('');
    setTint('');
    setScene('');
  };

  const save = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const look = await petsService.saveLook(pet._id, draft);
      queryClient.setQueryData<Pet[]>(['pets'], (pets) => pets?.map((p) => (p._id === pet._id ? { ...p, look } : p)));
      showToast.success('Оформление сохранено');
      navigate('/settings');
    } catch {
      showToast.failure('Не удалось сохранить оформление');
    } finally {
      if (mountedRef.current) setSaving(false);
    }
  };

  return (
    // The page itself wears the feed's look: what is chosen below shows behind it as it will behind the feed.
    <div
      className="page-container"
      data-pet-accent={petAccentAttr(draft)['data-pet-accent'] ?? 'none'}
      data-pet-tint={tintAttr['data-pet-tint'] ?? 'none'}
      style={{ background: petSceneStyle(draft).background ?? 'var(--app-page-background)' }}
    >
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Оформление питомца</h1>
          <p style={{ margin: 'var(--spacing-sm) 0 0', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
            Питомец: {pet.name}. Оформление видят все, у кого есть доступ к питомцу, и каждый из них может его поменять
          </p>
        </div>

        <div style={{ padding: '0 var(--spacing-md)' }}>
          <PetSummaryCard pet={pet} look={draft} />

          <Block title="Готовые образы">
            <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', padding: '12px 2px 4px' }}>
              {PET_VIBES.map((v) => (
                <button
                  key={v.key}
                  type="button"
                  className="tap-feedback"
                  onClick={() => applyVibe(v)}
                  style={{
                    flexShrink: 0,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    minHeight: 'var(--touch-min)',
                    padding: '0 14px',
                    borderRadius: '999px',
                    border: '1px solid var(--app-border-color)',
                    background: 'var(--app-page-background)',
                    color: 'var(--app-text-primary)',
                    fontFamily: 'inherit',
                    fontSize: 'var(--text-sm)',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  <span aria-hidden style={{ width: '14px', height: '14px', borderRadius: '50%', background: PET_ACCENTS.find((a) => a.key === v.look.accent)?.swatch }} />
                  {v.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="tap-feedback"
              onClick={reset}
              style={{ marginTop: '8px', minHeight: 'var(--touch-min)', padding: 0, border: 'none', background: 'none', font: 'inherit', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-accent-deep)', cursor: 'pointer' }}
            >
              Сбросить оформление
            </button>
          </Block>

          <Block title="Подпись и цвет">
            <label htmlFor="pet-tagline" style={labelStyle}>
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
            <Swatches label="Цвет питомца" value={accent} onChange={setAccent} noneLabel="Терракот" />
          </Block>

          <Block title="Имя и фото">
            <div id="pet-font-label" style={labelStyle}>
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
                      color: 'var(--app-text-primary)',
                      fontFamily: 'inherit',
                      fontSize: 'var(--text-lg)',
                      fontWeight: 700,
                      textAlign: 'center',
                      cursor: 'pointer',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      ...optionState(on),
                      ...petFontStyle(face, 'var(--text-lg)'),
                    }}
                  >
                    {pet.name}
                  </button>
                );
              })}
            </div>

            <div style={labelStyle}>
              Рамка фото
            </div>
            {PET_FRAME_GROUPS.map((g) => (
              <div key={g.key} role="radiogroup" aria-label={`Рамка: ${g.label}`} style={{ marginBottom: '12px' }}>
                <div aria-hidden style={{ fontSize: 'var(--text-xs)', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--app-text-secondary)', margin: '4px 2px 6px' }}>
                  {g.label}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '8px' }}>
                  {[...(g.key === 'style' ? [{ key: '', label: 'Без рамки', group: 'style' }] : []), ...PET_FRAMES.filter((f) => f.group === g.key)].map((f) => {
                    const on = frame === f.key;
                    const sample = petFrameStyle(f.key, 0.45);
                    return (
                      <button key={f.key || 'plain'} type="button" role="radio" aria-checked={on} className="tap-feedback" onClick={() => setFrame(f.key)} style={{ ...optionBase, gap: '8px', ...optionState(on) }}>
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
                            <PetPhotoFill src={pet.photo_url} alt="" size={44} species={pet.species} crop={crops[f.key]} style={sample.image} />
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
            ))}
            {frame && pet.photo_url && (
              <button
                type="button"
                className="tap-feedback"
                onClick={() => setCropping(frame)}
                style={{
                  width: '100%',
                  minHeight: 'var(--touch-min)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--app-border-color)',
                  background: 'var(--app-card-background)',
                  color: 'var(--app-text-primary)',
                  fontFamily: 'inherit',
                  fontSize: 'var(--text-md)',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Кадрировать фото под рамку
              </button>
            )}
          </Block>

          <Block title="Подложка карточки">
            <BackdropGrid label="Узор" items={PET_BACKDROPS.filter((b) => b.key !== 'photo' || pet.photo_url)} value={petBackdropKey(draft)} onChange={setBackdrop} hex={hex} photoUrl={pet.photo_url} tintAttr={tintAttr} />
            <Swatches label="Цвет подложки" value={tint} onChange={setTint} noneLabel="Как у питомца" />
          </Block>

          <Block title="Фон ленты">
            <p style={{ margin: '8px 0 0', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
              Что за записями этого питомца, пока открыта его лента. Тот же цвет подложки
            </p>
            <BackdropGrid label="Узор фона" items={[{ key: '', label: 'Без фона' }, ...PET_SCENES.filter((b) => b.key !== 'plain')]} value={scene} onChange={setScene} hex={hex} tintAttr={tintAttr} />
          </Block>

          <div style={{ paddingBottom: 'var(--spacing-md)' }}>
            <SpinnerButton type="button" block loading={saving} onClick={save}>
              Сохранить
            </SpinnerButton>
          </div>
        </div>
      </div>
      {cropping && pet.photo_url && (
        <FrameCropModal
          src={pet.photo_url}
          species={pet.species}
          frame={cropping}
          initial={crops[cropping]}
          onCancel={() => setCropping(null)}
          onDone={(crop) => {
            setCrops((prev) => ({ ...prev, [cropping]: crop }));
            setFrame(cropping);
            setCropping(null);
          }}
        />
      )}
    </div>
  );
}

import { useEffect, useRef, useState, type CSSProperties } from 'react';
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
  petBackdropKey,
  petBackdropStyle,
  petFontStyle,
  petFrameStyle,
  petLookOf,
  petAccentHex,
  type PetCrop,
  type PetLook,
} from '../utils/petLook';
import { setPetLookPreview } from '../utils/petLookPreview';
import { rovingKeyDown, rovingTabIndex } from '../utils/roving';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { showToast } from '../utils/toast';

/** Columns of option tiles: four on a phone, fewer when the text is large, so a label is never cut. */
const OPTION_GRID = 'repeat(auto-fill, minmax(max(5rem, 22%), 1fr))';

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
  // The look is the owner's to set; the family sees it. A link or a stale tab does not get a member into the editor.
  if (getSelectedPet.current_user_is_owner === false) return <OwnerOnly name={getSelectedPet.name} />;
  // Keyed by the pet: choosing another pet in the switcher opens that pet's own card.
  return <PetLookFor key={getSelectedPet._id} pet={getSelectedPet} />;
}

function OwnerOnly({ name }: { name: string }) {
  const navigate = useNavigate();
  return (
    <div className="page-container">
      <div className="max-width-container safe-area-padding">
        <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Оформление питомца</h1>
        <p style={{ margin: 'var(--spacing-md) 0', fontSize: 'var(--text-md)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
          Питомец: {name}. Оформление меняет только владелец, вы видите его таким, каким его выбрали
        </p>
        <SpinnerButton type="button" block loading={false} onClick={() => navigate('/settings')}>
          В настройки
        </SpinnerButton>
      </div>
    </div>
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
      <div role="radiogroup" aria-labelledby={id} onKeyDown={rovingKeyDown} style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
        {[{ ...BRAND, label: noneLabel }, ...PET_ACCENTS].map((a, i) => {
          const on = value === a.key;
          return (
            <button
              key={a.key || 'none'}
              type="button"
              role="radio"
              aria-checked={on}
              tabIndex={rovingTabIndex(on, i === 0, true)}
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

/** A grid of backdrops, each drawn as a small sample of itself in the pet's colour. */
function BackdropGrid({
  label,
  items,
  value,
  onChange,
  hex,
  photoUrl,
}: {
  label: string;
  items: readonly { key: string; label: string }[];
  value: string;
  onChange: (key: string) => void;
  hex: string;
  photoUrl?: string;
}) {
  const id = `bd-${label}`;
  return (
    <>
      <div id={id} style={labelStyle}>
        {label}
      </div>
      <div role="radiogroup" aria-labelledby={id} onKeyDown={rovingKeyDown} style={{ display: 'grid', gridTemplateColumns: OPTION_GRID, gap: '8px' }}>
        {items.map((b, i) => {
          const on = value === b.key;
          return (
            <button key={b.key} type="button" role="radio" aria-checked={on} tabIndex={rovingTabIndex(on, i === 0, items.some((x) => x.key === value))} className="tap-feedback" onClick={() => onChange(b.key)} style={{ ...optionBase, ...optionState(on) }}>
              <span
                aria-hidden
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

const TABS = [
  { key: 'vibes', label: 'Образы' },
  { key: 'color', label: 'Цвет' },
  { key: 'name', label: 'Имя' },
  { key: 'frame', label: 'Рамка' },
  { key: 'card', label: 'Подложка' },
  { key: 'scene', label: 'Фон' },
] as const;
type TabKey = (typeof TABS)[number]['key'];

const hint: CSSProperties = { margin: '8px 0 0', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' };

/** What to change, one at a time: the card above stays in view, so each change is seen where it is made. */
function TabStrip({ value, onChange }: { value: TabKey; onChange: (key: TabKey) => void }) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const move = (key: TabKey) => {
    onChange(key);
    refs.current[key]?.focus();
  };
  return (
    <div role="tablist" aria-label="Что менять" style={{ display: 'flex', gap: '4px', overflowX: 'auto', scrollbarWidth: 'none', padding: '2px 0' }}>
      {TABS.map((t, i) => {
        const on = value === t.key;
        return (
          <button
            key={t.key}
            ref={(el) => {
              refs.current[t.key] = el;
            }}
            type="button"
            role="tab"
            id={`look-tab-${t.key}`}
            aria-selected={on}
            aria-controls="look-panel"
            tabIndex={on ? 0 : -1}
            onClick={() => onChange(t.key)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowRight') move(TABS[(i + 1) % TABS.length].key);
              else if (e.key === 'ArrowLeft') move(TABS[(i + TABS.length - 1) % TABS.length].key);
              else if (e.key === 'Home') move(TABS[0].key);
              else if (e.key === 'End') move(TABS[TABS.length - 1].key);
              else return;
              e.preventDefault();
            }}
            className="tap-feedback"
            style={{
              flex: '1 0 auto',
              minHeight: 'var(--touch-min)',
              padding: '0 14px',
              border: 'none',
              borderBottom: on ? '3px solid var(--app-accent-deep)' : '3px solid transparent',
              background: 'none',
              color: on ? 'var(--app-accent-deep)' : 'var(--app-text-secondary)',
              fontFamily: 'inherit',
              fontSize: 'var(--text-md)',
              fontWeight: 600,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

function PetLookFor({ pet }: { pet: Pet }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const saved = petLookOf(pet);
  const [tab, setTab] = useState<TabKey>('vibes');
  const [tagline, setTagline] = useState(saved.tagline ?? '');
  const [accent, setAccent] = useState(saved.accent ?? '');
  const [font, setFont] = useState(saved.font ?? '');
  const [frame, setFrame] = useState(saved.frame ?? '');
  const [crops, setCrops] = useState<Record<string, PetCrop>>(saved.crops ?? {});
  // Empty keeps the default (a tint of the pet's colour, none without one); the grid shows what that comes to.
  const [backdrop, setBackdrop] = useState(saved.backdrop ?? '');
  const [scene, setScene] = useState(saved.scene ?? '');
  // The frame being cropped, from the button under the frames: each frame has a window of its own shape and its own crop.
  const [cropping, setCropping] = useState<string | null>(null);
  const SpeciesIcon = getSpecies(pet.species).icon;
  const [saving, setSaving] = useState(false);
  const mountedRef = useRef(true);
  const pinRef = useRef<HTMLDivElement | null>(null);

  const draft: PetLook = { tagline: tagline.trim(), accent, font, frame, crops, backdrop, scene };
  const hex = petAccentHex(draft);

  // The options show the name in each face, so they are fetched when that tab is opened and not before (about 320 KB).
  useEffect(() => {
    if (tab === 'name') PET_FONTS.forEach((f) => void loadPetFont(f));
  }, [tab]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // With large text the card and the tabs would fill the screen: then they scroll with the page instead of staying pinned.
  useEffect(() => {
    const el = pinRef.current;
    if (!el) return;
    const check = () => el.setAttribute('data-unpinned', String(el.offsetHeight > window.innerHeight * 0.4));
    check();
    const observer = new ResizeObserver(check);
    observer.observe(el);
    window.addEventListener('resize', check);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', check);
    };
  }, []);

  // The whole app shows the draft while this page is open, and the saved look again when it closes.
  const draftKey = JSON.stringify(draft);
  useEffect(() => {
    setPetLookPreview(JSON.parse(draftKey) as PetLook);
  }, [draftKey]);
  useEffect(() => () => setPetLookPreview(null), []);


  const applyVibe = (v: (typeof PET_VIBES)[number]) => {
    setAccent(v.look.accent);
    setFont(v.look.font);
    setBackdrop(v.look.backdrop);
    setScene(v.look.scene);
    setFrame(v.look.frame);
  };

  const reset = () => {
    setAccent('');
    setFont('');
    setFrame('');
    setBackdrop('');
    setScene('');
  };

  // What has been changed and not saved: the screen asks before it is left, like the app's other forms.
  const snapshot = (l: PetLook) => JSON.stringify([l.tagline ?? '', l.accent ?? '', l.font ?? '', l.frame ?? '', l.backdrop ?? '', l.scene ?? '', l.crops ?? {}]);
  const dirty = snapshot(draft) !== snapshot(saved);
  const { dialog: leaveDialog, release } = useUnsavedChangesGuard(dirty);

  const save = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const look = await petsService.saveLook(pet._id, draft);
      queryClient.setQueryData<Pet[]>(['pets'], (pets) => pets?.map((p) => (p._id === pet._id ? { ...p, look } : p)));
      showToast.success('Оформление сохранено');
      release();
      navigate('/settings');
    } catch {
      showToast.failure('Не удалось сохранить оформление');
    } finally {
      if (mountedRef.current) setSaving(false);
    }
  };

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-md)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Оформление питомца</h1>
          <p style={{ margin: 'var(--spacing-sm) 0 0', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
            Питомец: {pet.name}. Оформление видят все, у кого есть доступ к питомцу, а менять его можете только вы
          </p>
        </div>

        <div style={{ padding: '0 var(--spacing-md)' }}>
          {/* The card and the switch of what to change stay in view while the options scroll beneath them. */}
          <div className="look-sticky" ref={pinRef}>
            <PetSummaryCard pet={pet} look={draft} compact />
            <TabStrip value={tab} onChange={setTab} />
          </div>

          <section id="look-panel" role="tabpanel" aria-labelledby={`look-tab-${tab}`} className="card-soft" style={{ padding: '16px', marginTop: 'var(--spacing-sm)', marginBottom: 'var(--spacing-md)' }}>
            {tab === 'vibes' && (
              <>
                <p style={{ ...hint, margin: 0 }}>Готовый набор одним нажатием: цвет, шрифт, рамка и фон. Потом можно поменять по отдельности</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', padding: '12px 0 4px' }}>
                  {PET_VIBES.map((v) => (
                    <button
                      key={v.key}
                      type="button"
                      className="tap-feedback"
                      onClick={() => applyVibe(v)}
                      style={{
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
                  style={{ marginTop: '4px', minHeight: 'var(--touch-min)', padding: 0, border: 'none', background: 'none', font: 'inherit', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-accent-deep)', cursor: 'pointer' }}
                >
                  Сбросить оформление
                </button>
              </>
            )}

            {tab === 'color' && (
              <>
                <p style={{ ...hint, margin: 0 }}>Цвет питомца виден на его карточке и в акцентах приложения, пока выбран этот питомец</p>
                <Swatches label="Цвет питомца" value={accent} onChange={setAccent} noneLabel="Терракот" />
              </>
            )}

            {tab === 'name' && (
              <>
                <label htmlFor="pet-tagline" style={{ ...labelStyle, marginTop: 0 }}>
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
                <div style={{ marginTop: 'var(--spacing-xs)', fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)', textAlign: 'right' }}>
                  {tagline.length} из {PET_TAGLINE_MAX}
                </div>

                <div id="pet-font-label" style={labelStyle}>
                  Шрифт имени
                </div>
                <div role="radiogroup" aria-labelledby="pet-font-label" onKeyDown={rovingKeyDown} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(max(9rem, 44%), 1fr))', gap: '8px' }}>
                  {[{ key: '', label: 'Обычный', family: '', weight: 700, scale: 1 }, ...PET_FONTS].map((f, i) => {
                    const on = font === f.key;
                    const face = PET_FONTS.find((x) => x.key === f.key);
                    return (
                      <button
                        key={f.key || 'plain'}
                        type="button"
                        role="radio"
                        aria-checked={on}
                        tabIndex={rovingTabIndex(on, i === 0, font === '' || PET_FONTS.some((x) => x.key === font))}
                        aria-label={`${pet.name}, ${f.label}`}
                        className="tap-feedback"
                        onClick={() => setFont(f.key)}
                        style={{
                          // One height for every face (it also scales with the text size): the name sits in the middle,
                          // and the line of each face is tall enough for its letters (PET_FONTS line).
                          height: '3.25rem',
                          padding: '0 12px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          borderRadius: 'var(--radius-md)',
                          color: 'var(--app-text-primary)',
                          fontFamily: 'inherit',
                          fontSize: 'var(--text-lg)',
                          fontWeight: 700,
                          textAlign: 'center',
                          cursor: 'pointer',
                          overflow: 'hidden',
                          ...optionState(on),
                          ...petFontStyle(face, 'var(--text-lg)'),
                        }}
                      >
                        <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{pet.name}</span>
                      </button>
                    );
                  })}
                </div>
              </>
            )}

            {tab === 'frame' && (
              <>
                {PET_FRAME_GROUPS.map((g) => (
                  <div key={g.key} role="radiogroup" aria-label={`Рамка: ${g.label}`} onKeyDown={rovingKeyDown} style={{ marginBottom: '12px' }}>
                    <div aria-hidden style={{ fontSize: 'var(--text-xs)', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--app-text-secondary)', margin: 'var(--spacing-xs) var(--spacing-xs) var(--spacing-sm)' }}>
                      {g.label}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: OPTION_GRID, gap: '8px' }}>
                      {[...(g.key === 'style' ? [{ key: '', label: 'Без рамки', group: 'style' }] : []), ...PET_FRAMES.filter((f) => f.group === g.key)].map((f, i, list) => {
                        const on = frame === f.key;
                        const sample = petFrameStyle(f.key, 0.45);
                        return (
                          <button key={f.key || 'plain'} type="button" role="radio" aria-checked={on} tabIndex={rovingTabIndex(on, i === 0, list.some((x) => x.key === frame))} className="tap-feedback" onClick={() => setFrame(f.key)} style={{ ...optionBase, gap: '8px', ...optionState(on) }}>
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
              </>
            )}

            {tab === 'card' && (
              <>
                <BackdropGrid label="Узор" items={PET_BACKDROPS.filter((b) => b.key !== 'photo' || pet.photo_url)} value={petBackdropKey(draft)} onChange={setBackdrop} hex={hex} photoUrl={pet.photo_url} />
              </>
            )}

            {tab === 'scene' && (
              <>
                <p style={{ ...hint, margin: 0 }}>Фон за записями на всех экранах этого питомца, в цвете питомца</p>
                <BackdropGrid label="Узор фона" items={[{ key: '', label: 'Без фона' }, ...PET_SCENES.filter((b) => b.key !== 'plain')]} value={scene} onChange={setScene} hex={hex} />
              </>
            )}
          </section>

          <div style={{ paddingBottom: 'var(--spacing-md)' }}>
            <SpinnerButton type="button" block loading={saving} onClick={save}>
              Сохранить
            </SpinnerButton>
          </div>
        </div>
      </div>
      {leaveDialog}
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

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Button, DatePicker, Dialog, Input } from 'antd-mobile';
import {
  Archive,
  Bell,
  Bird,
  Cake,
  Camera,
  Cat,
  ChevronLeft,
  Dog,
  FileText,
  Fish,
  Footprints,
  PawPrint,
  Pill,
  Scale,
  Share,
  SquarePlus,
  Users,
  Utensils,
  type LucideIcon,
} from 'lucide-react';

import { usePet } from '../hooks/usePet';
import { useSession } from '../hooks/useSession';
import { petsService, type Pet } from '../services/pets.service';
import { getPushSubscriptionState, isPushSupported, needsHomeScreenForPush, subscribeToPush } from '../utils/pushNotifications';
import { computePetAge, MONTHS_GENITIVE } from '../utils/relativeTime';
import { dismissOnboarding } from '../utils/onboarding';
import { getApiErrorMessage } from '../utils/apiError';
import { hapticFeedback } from '../utils/haptic';
import { showToast } from '../utils/toast';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { PhotoCropModal } from '../components/PhotoCropModal';
import './Onboarding.css';

type StepId = 'welcome' | 'diary' | 'care' | 'family' | 'species' | 'name' | 'notify' | 'install' | 'done';
type SpeciesKey = 'cat' | 'dog' | 'bird' | 'fish' | 'other';

const INTRO_STEPS: StepId[] = ['welcome', 'diary', 'care', 'family'];

const SPECIES: { key: SpeciesKey; label: string; icon: LucideIcon; question: string }[] = [
  { key: 'cat', label: 'Кот', icon: Cat, question: 'Как зовут вашего кота?' },
  { key: 'dog', label: 'Собака', icon: Dog, question: 'Как зовут вашу собаку?' },
  { key: 'bird', label: 'Птица', icon: Bird, question: 'Как зовут вашу птицу?' },
  { key: 'fish', label: 'Рыбка', icon: Fish, question: 'Как зовут вашу рыбку?' },
  { key: 'other', label: 'Другой питомец', icon: PawPrint, question: 'Как зовут вашего питомца?' },
];

const MONTHS_NOMINATIVE = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];

const speciesGradient = (key: SpeciesKey | null) =>
  `var(--species-gradient-${key && key !== 'other' ? key : 'default'})`;

const toIsoDate = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

const floatDelay = (ms: number) => ({ '--d': `${ms}ms` }) as CSSProperties;

/** Waits for the pet roster before deciding which flow this is: a user who
 *  already has pets only gets the intro slides (a replay), a brand-new one
 *  goes on to add their first pet. Decided once, up front — the roster
 *  changes mid-flow the moment that first pet is created. */
export function Onboarding() {
  const { pets, isFetched } = usePet();
  const [searchParams] = useSearchParams();
  if (!isFetched) return <LoadingSpinner />;
  return <OnboardingFlow initialReplay={searchParams.get('replay') === '1' || pets.length > 0} />;
}

function OnboardingFlow({ initialReplay }: { initialReplay: boolean }) {
  // Frozen on mount: the parent re-renders with pets.length === 1 as soon
  // as the first pet is created, which would otherwise flip this into a
  // replay mid-flow and yank the user back to the intro slides.
  const [replay] = useState(initialReplay);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { selectPet } = usePet();
  const { username } = useSession();

  // 'install': Safari on iPhone, where push only works once Petzy is on
  // the Home Screen; the step says how instead of silently skipping.
  const [pushState, setPushState] = useState<'unknown' | 'offerable' | 'install' | 'skip'>(
    () => (isPushSupported() ? 'unknown' : needsHomeScreenForPush() ? 'install' : 'skip'),
  );
  useEffect(() => {
    if (pushState !== 'unknown') return;
    let cancelled = false;
    getPushSubscriptionState()
      .then((s) => { if (!cancelled) setPushState(s === 'off' ? 'offerable' : 'skip'); })
      .catch(() => { if (!cancelled) setPushState('skip'); });
    return () => { cancelled = true; };
  }, [pushState]);

  const steps: StepId[] = replay
    ? INTRO_STEPS
    : [
        ...INTRO_STEPS,
        'species',
        'name',
        ...(pushState === 'offerable' ? (['notify'] as StepId[]) : pushState === 'install' ? (['install'] as StepId[]) : []),
        'done',
      ];

  const [index, setIndex] = useState(0);
  const step = steps[Math.min(index, steps.length - 1)];

  const [species, setSpecies] = useState<SpeciesKey | null>(null);
  const [name, setName] = useState('');
  const [birthDate, setBirthDate] = useState('');
  const [datePickerVisible, setDatePickerVisible] = useState(false);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [cropTarget, setCropTarget] = useState<{ src: string; filename: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [saving, setSaving] = useState(false);
  const [createdPet, setCreatedPet] = useState<Pet | null>(null);
  const [enablingPush, setEnablingPush] = useState(false);

  useEffect(() => () => { if (photoPreview) URL.revokeObjectURL(photoPreview); }, [photoPreview]);

  const go = (target: number) => {
    const clamped = Math.max(0, Math.min(target, steps.length - 1));
    if (clamped === index) return;
    setIndex(clamped);
    hapticFeedback('light');
  };
  const next = () => go(index + 1);
  const back = () => go(index - 1);
  const finishIntro = () => {
    if (!replay) {
      go(steps.indexOf('species'));
      return;
    }
    // Replays are opened from Settings; a direct link has nowhere to go
    // back to, so land on the dashboard instead of leaving the app.
    if ((window.history.state?.idx ?? 0) > 0) navigate(-1);
    else navigate('/', { replace: true });
  };

  const isIntro = INTRO_STEPS.includes(step);
  // Once the pet exists, stepping back into the name form would only
  // offer to create a second one.
  const canGoBack = index > 0 && step !== 'done' && !(createdPet && step === 'notify');

  // Horizontal swipe between intro slides, like every carousel onboarding.
  const touchStart = useRef<{ x: number; y: number } | null>(null);
  const onTouchStart = (e: React.TouchEvent) => {
    const t = e.touches[0];
    touchStart.current = { x: t.clientX, y: t.clientY };
  };
  const onTouchEnd = (e: React.TouchEvent) => {
    const start = touchStart.current;
    touchStart.current = null;
    if (!start || !isIntro) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - start.x;
    const dy = t.clientY - start.y;
    if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy)) return;
    if (dx < 0) {
      if (step === 'family') finishIntro();
      else next();
    } else {
      back();
    }
  };

  const pickSpecies = (key: SpeciesKey) => {
    setSpecies(key);
    hapticFeedback('medium');
    window.setTimeout(() => go(steps.indexOf('name')), 260);
  };

  const onPhotoChosen = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setCropTarget({ src: URL.createObjectURL(file), filename: file.name });
  };

  const createPet = async () => {
    const trimmed = name.trim();
    if (!trimmed || saving) return;
    setSaving(true);
    try {
      const pet = await petsService.createPet({
        name: trimmed,
        species: species ?? undefined,
        birth_date: birthDate || undefined,
        photo_file: photoFile ?? undefined,
      });
      await queryClient.invalidateQueries({ queryKey: ['pets'] });
      selectPet(pet);
      setCreatedPet(pet);
      hapticFeedback('medium');
      next();
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось добавить питомца'));
    } finally {
      setSaving(false);
    }
  };

  const enablePush = async () => {
    setEnablingPush(true);
    try {
      await subscribeToPush();
      showToast.success('Уведомления включены');
      next();
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось включить уведомления'));
    } finally {
      setEnablingPush(false);
    }
  };

  const waitForShare = async () => {
    const confirmed = await Dialog.confirm({
      title: 'С вами поделятся питомцем?',
      content: (
        <div style={{ textAlign: 'center', lineHeight: 1.5 }}>
          Попросите владельца открыть питомца и выбрать «Поделиться доступом».
          Ваш логин: <strong>{username}</strong>. Питомец появится у вас сам
        </div>
      ),
      confirmText: 'Понятно',
      cancelText: 'Добавлю своего',
    });
    if (!confirmed) return;
    dismissOnboarding(username);
    navigate('/', { replace: true });
  };

  const speciesMeta = SPECIES.find((s) => s.key === species) ?? SPECIES[SPECIES.length - 1];
  const SpeciesIcon = speciesMeta.icon;
  const displayName = (createdPet?.name ?? name.trim()) || 'Питомец';
  const avatarPhoto = createdPet?.photo_url ?? photoPreview;

  // ── Per-step content ───────────────────────────────────────────────
  let art: ReactNode = null;
  let title: ReactNode = '';
  let lead: ReactNode = '';
  let body: ReactNode = null;
  let cta: ReactNode = null;
  let secondary: ReactNode = null;

  const ctaButton = (label: string, onClick: () => void, opts: { loading?: boolean; disabled?: boolean } = {}) => (
    <Button
      block
      className="onb__cta"
      onClick={onClick}
      loading={opts.loading}
      disabled={opts.disabled || opts.loading}
    >
      {label}
    </Button>
  );

  switch (step) {
    case 'welcome':
      art = <WelcomeArt />;
      title = 'Забота о питомце в одном месте';
      lead = 'Кормление, вес, лекарства и документы без блокнотов и напоминалок в телефоне';
      cta = ctaButton('Начать', next);
      break;
    case 'diary':
      art = <DiaryArt />;
      title = 'Все записи о питомце в одной ленте';
      lead = 'Отмечайте кормление, вес и уход в пару касаний, а для остального заведите свои события, например прогулки';
      cta = ctaButton('Дальше', next);
      break;
    case 'care':
      art = <CareArt />;
      title = 'Напомнит и подскажет';
      lead = 'Уведомление, когда пора дать лекарство, и сигнал, если вес или аппетит резко изменились';
      cta = ctaButton('Дальше', next);
      break;
    case 'family':
      art = <FamilyArt />;
      title = 'Документы и семья рядом';
      lead = 'Храните здесь справки, анализы и снимки МРТ или КТ. Откройте доступ близким, и все будут видеть одно и то же';
      cta = ctaButton(replay ? 'Понятно' : 'Добавить питомца', finishIntro);
      break;
    case 'species':
      title = 'Кто живёт у вас?';
      lead = 'Начнём знакомство. Остальное можно заполнить позже';
      body = (
        <div className="onb__species-grid" role="group" aria-label="Вид питомца">
          {SPECIES.map((s, i) => {
            const Icon = s.icon;
            const wide = s.key === 'other';
            return (
              <button
                key={s.key}
                type="button"
                className={`onb__species tap-feedback${wide ? ' onb__species--wide' : ''}`}
                style={floatDelay(80 + i * 60)}
                aria-pressed={species === s.key}
                onClick={() => pickSpecies(s.key)}
              >
                <span className="onb__species-icon" style={{ background: speciesGradient(s.key) }}>
                  <Icon size={wide ? 22 : 30} strokeWidth={2} />
                </span>
                {s.label}
              </button>
            );
          })}
        </div>
      );
      secondary = (
        <button type="button" className="onb__secondary tap-feedback" onClick={waitForShare}>
          Со мной поделятся питомцем
        </button>
      );
      break;
    case 'name': {
      const age = birthDate ? computePetAge(birthDate) : '';
      const [y, m, d] = birthDate.split('-').map(Number);
      art = (
        <button
          type="button"
          className="onb__avatar-btn onb-float tap-feedback"
          style={{ background: speciesGradient(species) }}
          onClick={() => fileInputRef.current?.click()}
          aria-label={photoPreview ? 'Сменить фото' : 'Добавить фото'}
        >
          {photoPreview ? <img src={photoPreview} alt="" /> : <SpeciesIcon size={56} strokeWidth={1.75} />}
          <span className="onb__avatar-badge" aria-hidden>
            <Camera size={18} strokeWidth={2.2} />
          </span>
        </button>
      );
      title = speciesMeta.question;
      lead = 'Добавьте фото: так питомца легче узнать в ленте';
      body = (
        <>
          <Input
            className="onb__name-input"
            value={name}
            onChange={setName}
            placeholder="Имя"
            maxLength={50}
            autoFocus
            enterKeyHint="done"
            onEnterPress={createPet}
            aria-label="Имя питомца"
          />
          <button
            type="button"
            className="onb__chip tap-feedback"
            data-filled={!!birthDate}
            onClick={() => setDatePickerVisible(true)}
          >
            <Cake size={16} strokeWidth={2} />
            {birthDate ? `${d} ${MONTHS_GENITIVE[m - 1]} ${y}${age ? `, ${age}` : ''}` : 'Добавить день рождения'}
          </button>
          <DatePicker
            visible={datePickerVisible}
            onClose={() => setDatePickerVisible(false)}
            precision="day"
            min={new Date(new Date().getFullYear() - 30, 0, 1)}
            max={new Date()}
            defaultValue={new Date(new Date().getFullYear() - 1, new Date().getMonth(), new Date().getDate())}
            renderLabel={(type, value) => (type === 'month' ? MONTHS_NOMINATIVE[value - 1] : String(value))}
            onConfirm={(date) => setBirthDate(toIsoDate(date))}
            title="День рождения"
            cancelText="Отмена"
            confirmText="Готово"
          />
          <input ref={fileInputRef} type="file" accept="image/*" hidden onChange={onPhotoChosen} />
        </>
      );
      cta = ctaButton('Дальше', createPet, { loading: saving, disabled: !name.trim() });
      break;
    }
    case 'notify':
      art = (
        <div className="onb-stack">
          <div className="onb-bell onb-float" style={floatDelay(0)}>
            <Bell size={52} strokeWidth={1.75} />
          </div>
          <NotificationMock
            delay={220}
            title="Пора дать лекарство"
            body="Синулокс, 08:00"
          />
        </div>
      );
      title = 'Включить уведомления?';
      lead = 'Напомним о лекарствах и истекающих документах, сообщим о необычных показателях';
      cta = ctaButton('Включить', enablePush, { loading: enablingPush });
      secondary = (
        <button type="button" className="onb__secondary tap-feedback" onClick={next}>
          Не сейчас
        </button>
      );
      break;
    case 'install':
      art = (
        <div className="onb-stack">
          <div className="onb-bell onb-float" style={floatDelay(0)}>
            <Bell size={52} strokeWidth={1.75} />
          </div>
          <NotificationMock
            delay={220}
            title="Пора дать лекарство"
            body="Синулокс, 08:00"
          />
        </div>
      );
      title = 'Напоминания на iPhone';
      lead = 'Safari присылает уведомления только приложениям с экрана «Домой». Добавьте туда Petzy, и напоминания заработают';
      body = (
        <ol className="onb-howto">
          <li>
            <Share size={20} strokeWidth={2} aria-hidden />
            <span>Нажмите «Поделиться» в панели Safari</span>
          </li>
          <li>
            <SquarePlus size={20} strokeWidth={2} aria-hidden />
            <span>Выберите «На экран „Домой“» и откройте Petzy оттуда</span>
          </li>
        </ol>
      );
      cta = ctaButton('Понятно', next);
      break;
    case 'done':
      art = (
        <div className="onb-done">
          {[0, 600, 1200].map((delay) => (
            <span key={delay} className="onb-done__ring" style={floatDelay(delay)} />
          ))}
          <Confetti />
          <div className="onb-done__avatar" style={{ background: speciesGradient(species) }}>
            {avatarPhoto ? <img src={avatarPhoto} alt="" /> : <SpeciesIcon size={60} strokeWidth={1.75} />}
          </div>
        </div>
      );
      title = `${displayName} теперь в Petzy`;
      lead = 'Добавьте первую запись, например сегодняшнее кормление';
      // Straight into the first real record: the feed underneath, so
      // saving the form lands there rather than back in onboarding.
      cta = ctaButton('Записать кормление', () => {
        navigate('/', { replace: true });
        navigate('/form/feeding');
      });
      secondary = (
        <button type="button" className="onb__secondary tap-feedback" onClick={() => navigate('/', { replace: true })}>
          Открыть ленту
        </button>
      );
      break;
  }

  const progressSteps = steps.filter((s) => s !== 'done');

  return (
    <div className="onb" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
      <div className="onb__glow" aria-hidden />

      {step !== 'done' && (
        <div className="onb__top">
          {canGoBack ? (
            <button type="button" className="onb__icon-btn tap-feedback" onClick={back} aria-label="Назад">
              <ChevronLeft size={24} strokeWidth={2.2} />
            </button>
          ) : (
            <span />
          )}
          <div
            className="onb__progress"
            role="progressbar"
            aria-label="Знакомство с Petzy"
            aria-valuetext={`Шаг ${Math.min(index + 1, progressSteps.length)} из ${progressSteps.length}`}
            aria-valuemin={1}
            aria-valuemax={progressSteps.length}
            aria-valuenow={Math.min(index + 1, progressSteps.length)}
          >
            {progressSteps.map((s, i) => (
              <div
                key={s}
                className="onb__progress-seg"
                data-state={i < index ? 'done' : i === index ? 'current' : 'todo'}
              >
                <span />
              </div>
            ))}
          </div>
          {isIntro ? (
            <button type="button" className="onb__text-btn tap-feedback touch-target" onClick={finishIntro}>
              {replay ? 'Закрыть' : 'Пропустить'}
            </button>
          ) : (
            <span />
          )}
        </div>
      )}

      <div className="onb__stage" key={step}>
        {art && <div className="onb__art">{art}</div>}
        <div className="onb__copy">
          <h1 className="onb__title">{title}</h1>
          <p className="onb__lead">{lead}</p>
        </div>
        {body}
      </div>

      <div className="onb__actions">
        {cta}
        {secondary}
      </div>

      {cropTarget && (
        <PhotoCropModal
          imageSrc={cropTarget.src}
          filename={cropTarget.filename}
          onCancel={() => {
            URL.revokeObjectURL(cropTarget.src);
            setCropTarget(null);
          }}
          onCropped={(file) => {
            URL.revokeObjectURL(cropTarget.src);
            setCropTarget(null);
            setPhotoFile(file);
            setPhotoPreview(URL.createObjectURL(file));
          }}
        />
      )}
    </div>
  );
}

// ── Illustrations: small, real-looking slices of the product rather than
// abstract art — the user sees what they're about to get. ──────────────

function WelcomeArt() {
  const bubbles: { icon: LucideIcon; species: SpeciesKey; pos: CSSProperties; small?: boolean; d: number }[] = [
    { icon: Cat, species: 'cat', pos: { top: '6%', left: '8%' }, d: 120 },
    { icon: Dog, species: 'dog', pos: { top: '2%', right: '10%' }, small: true, d: 220 },
    { icon: Bird, species: 'bird', pos: { bottom: '8%', left: '16%' }, small: true, d: 320 },
    { icon: Fish, species: 'fish', pos: { bottom: '4%', right: '6%' }, d: 420 },
  ];
  return (
    <>
      {bubbles.map(({ icon: Icon, species, pos, small, d }) => (
        <span
          key={species}
          className={`onb-bubble onb-float${small ? ' onb-bubble--sm' : ''}`}
          style={{ ...pos, ...floatDelay(d), background: speciesGradient(species) }}
          aria-hidden
        >
          <Icon size={small ? 22 : 28} strokeWidth={2} />
        </span>
      ))}
      <span className="onb-wordmark onb-float" style={floatDelay(0)}>Petzy</span>
    </>
  );
}

function EventCard({
  icon: Icon, tile, title, meta, time, delay,
}: { icon: LucideIcon; tile: string; title: string; meta: string; time: string; delay: number }) {
  return (
    <div className="onb-card onb-float" style={floatDelay(delay)}>
      <span className="onb-card__tile" style={{ background: `var(--tile-${tile})` }}>
        <Icon size={20} strokeWidth={2.2} />
      </span>
      <span className="onb-card__body">
        <span className="onb-card__title">{title}</span>
        <span className="onb-card__meta">{meta}</span>
      </span>
      <span className="onb-card__time">{time}</span>
    </div>
  );
}

function DiaryArt() {
  return (
    <div className="onb-stack" aria-hidden>
      <EventCard icon={Utensils} tile="brown" title="Кормление" meta="280 г корма" time="08:00" delay={0} />
      <EventCard icon={Scale} tile="orange" title="Вес" meta="4.6 кг" time="вчера" delay={140} />
      <EventCard icon={Footprints} tile="green" title="Прогулка" meta="45 минут" time="вчера" delay={280} />
    </div>
  );
}

function NotificationMock({ title, body, delay, extra }: { title: string; body: string; delay: number; extra?: ReactNode }) {
  return (
    <div className="onb-notif onb-float" style={floatDelay(delay)}>
      <div className="onb-notif__head">
        <img className="onb-notif__app" src="/icon-192.png" alt="" />
        Petzy
        <time>сейчас</time>
      </div>
      <div className="onb-notif__title">{title}</div>
      <div className="onb-notif__body">{body}</div>
      {extra}
    </div>
  );
}

function CareArt() {
  return (
    <div className="onb-stack" aria-hidden>
      <NotificationMock delay={0} title="Пора дать лекарство" body="Синулокс, 08:00" />
      <NotificationMock
        delay={160}
        title="Необычное значение: Вес"
        body="Барсик. Вес (кг): 5.4 (обычно ~4.6)"
        extra={
          <svg className="onb-spark" viewBox="0 0 260 44" preserveAspectRatio="none">
            <polyline
              points="0,30 40,29 80,31 120,28 160,30 200,29 244,8"
              fill="none"
              stroke="var(--app-accent)"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <circle cx="244" cy="8" r="5" fill="var(--app-accent)" />
          </svg>
        }
      />
      <span className="onb-chip onb-float" style={floatDelay(320)}>
        <Pill size={14} strokeWidth={2.2} /> Осталось 12 таблеток
      </span>
    </div>
  );
}

function FamilyArt() {
  return (
    <div className="onb-stack" aria-hidden>
      <div className="onb-card onb-float" style={floatDelay(0)}>
        <span className="onb-card__tile" style={{ background: 'var(--tile-blue)' }}>
          <FileText size={20} strokeWidth={2.2} />
        </span>
        <span className="onb-card__body">
          <span className="onb-card__title">Прививка от бешенства</span>
          <span className="onb-card__meta">Ветклиника «Айболит»</span>
        </span>
        <span className="onb-chip onb-chip--warn">до 16 янв</span>
      </div>
      <div className="onb-card onb-float" style={floatDelay(150)}>
        <span className="onb-card__tile onb-card__tile--film">
          <Archive size={20} strokeWidth={2.2} />
        </span>
        <span className="onb-card__body">
          <span className="onb-card__title">КТ грудной клетки</span>
          <span className="onb-card__meta">Архив со снимками</span>
        </span>
        <span className="onb-chip">312 МБ</span>
      </div>
      <div className="onb-card onb-float" style={floatDelay(300)}>
        <span className="onb-card__tile" style={{ background: 'var(--tile-pink)' }}>
          <Users size={20} strokeWidth={2.2} />
        </span>
        <span className="onb-card__body">
          <span className="onb-card__title">Общий доступ</span>
          <span className="onb-card__meta">Мама и Аня тоже видят записи</span>
        </span>
        <span className="onb-avatars">
          <span style={{ background: 'var(--tile-yellow)' }}>М</span>
          <span style={{ background: 'var(--tile-teal)' }}>А</span>
        </span>
      </div>
    </div>
  );
}

function Confetti() {
  const colors = ['var(--app-accent)', 'var(--tile-yellow)', 'var(--tile-green)', 'var(--tile-pink)', 'var(--tile-blue)', '#E8B558'];
  const pieces = Array.from({ length: 18 }, (_, i) => {
    const angle = (i / 18) * Math.PI * 2;
    const dist = 110 + (i % 3) * 28;
    return {
      '--x': `${Math.round(Math.cos(angle) * dist)}px`,
      '--y': `${Math.round(Math.sin(angle) * dist)}px`,
      '--r': `${(i % 2 ? 1 : -1) * (160 + i * 12)}deg`,
      '--d': `${(i % 4) * 40}ms`,
      '--c': colors[i % colors.length],
    } as CSSProperties;
  });
  return (
    <>
      {pieces.map((style, i) => (
        <span key={i} className="onb-confetti" style={style} aria-hidden />
      ))}
    </>
  );
}

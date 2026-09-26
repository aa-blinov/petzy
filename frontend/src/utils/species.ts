import { Bird, Cat, Dog, Fish, PawPrint, Rabbit, Rat, Squirrel, Turtle, type LucideIcon } from 'lucide-react';

/**
 * Every species the app knows, and everything that depends on it: the
 * name, the icon and placeholder gradient, how onboarding asks for the
 * name, whether neutering applies, what "breed" is called, and which of
 * the builtin events make sense by default.
 *
 * One list instead of five: the picker, onboarding, the pets list, the
 * pet switcher and the summary card each kept their own, and they had
 * drifted (a rabbit had a gradient but no way to pick it).
 */
export type SpeciesKey =
  | 'cat'
  | 'dog'
  | 'rabbit'
  | 'ferret'
  | 'guinea_pig'
  | 'chinchilla'
  | 'rat'
  | 'hamster'
  | 'bird'
  | 'fish'
  | 'turtle'
  | 'reptile'
  | 'other';

/** The builtin event types (web/builtin_event_types.py). */
type BuiltinEvent =
  | 'feeding'
  | 'weight'
  | 'defecation'
  | 'litter'
  | 'asthma'
  | 'eye_drops'
  | 'ear_cleaning'
  | 'tooth_brushing';

const ALL_EVENTS: BuiltinEvent[] = [
  'feeding', 'weight', 'defecation', 'litter', 'asthma', 'eye_drops', 'ear_cleaning', 'tooth_brushing',
];

export interface Species {
  key: SpeciesKey;
  label: string;
  /** Onboarding's name question: «Как зовут вашего кота?» */
  question: string;
  icon: LucideIcon;
  gradient: string;
  /** Castration/sterilisation is a thing for mammals, not for birds, fish or reptiles. */
  neutering: boolean;
  /** What «Порода» is called: fish and reptiles have species, not breeds. */
  breedLabel: string;
  breedPlaceholder: string;
  /** Builtin events shown by default for a new pet of this species. */
  events: BuiltinEvent[];
}

const GRADIENT = {
  cat: 'var(--species-gradient-cat)',
  dog: 'var(--species-gradient-dog)',
  bird: 'var(--species-gradient-bird)',
  fish: 'var(--species-gradient-fish)',
  rabbit: 'var(--species-gradient-rabbit)',
  reptile: 'var(--species-gradient-reptile)',
  small: 'var(--species-gradient-small)',
  default: 'var(--species-gradient-default)',
};

export const SPECIES: Species[] = [
  {
    key: 'cat', label: 'Кот', question: 'Как зовут вашего кота?', icon: Cat, gradient: GRADIENT.cat,
    neutering: true, breedLabel: 'Порода', breedPlaceholder: 'Например, британская',
    events: ALL_EVENTS,
  },
  {
    key: 'dog', label: 'Собака', question: 'Как зовут вашу собаку?', icon: Dog, gradient: GRADIENT.dog,
    neutering: true, breedLabel: 'Порода', breedPlaceholder: 'Например, лабрадор',
    events: ['feeding', 'weight', 'defecation', 'eye_drops', 'ear_cleaning', 'tooth_brushing'],
  },
  {
    key: 'rabbit', label: 'Кролик', question: 'Как зовут вашего кролика?', icon: Rabbit, gradient: GRADIENT.rabbit,
    neutering: true, breedLabel: 'Порода', breedPlaceholder: 'Например, карликовый',
    // Rabbit teeth grow all their life and are never brushed.
    events: ['feeding', 'weight', 'defecation', 'litter', 'eye_drops', 'ear_cleaning'],
  },
  {
    key: 'ferret', label: 'Хорёк', question: 'Как зовут вашего хорька?', icon: PawPrint, gradient: GRADIENT.small,
    neutering: true, breedLabel: 'Окрас', breedPlaceholder: 'Например, соболиный',
    events: ['feeding', 'weight', 'defecation', 'litter', 'eye_drops', 'ear_cleaning', 'tooth_brushing'],
  },
  {
    key: 'guinea_pig', label: 'Морская свинка', question: 'Как зовут вашу морскую свинку?', icon: PawPrint,
    gradient: GRADIENT.small, neutering: true, breedLabel: 'Порода', breedPlaceholder: 'Например, абиссинская',
    events: ['feeding', 'weight', 'defecation', 'litter', 'eye_drops'],
  },
  {
    key: 'chinchilla', label: 'Шиншилла', question: 'Как зовут вашу шиншиллу?', icon: Squirrel,
    gradient: GRADIENT.small, neutering: true, breedLabel: 'Окрас', breedPlaceholder: 'Например, стандартный серый',
    events: ['feeding', 'weight', 'defecation', 'litter', 'eye_drops'],
  },
  {
    key: 'rat', label: 'Крыса', question: 'Как зовут вашу крысу?', icon: Rat, gradient: GRADIENT.small,
    neutering: true, breedLabel: 'Порода', breedPlaceholder: 'Например, дамбо',
    events: ['feeding', 'weight', 'litter', 'eye_drops'],
  },
  {
    key: 'hamster', label: 'Хомяк', question: 'Как зовут вашего хомяка?', icon: Squirrel, gradient: GRADIENT.small,
    neutering: true, breedLabel: 'Порода', breedPlaceholder: 'Например, джунгарский',
    events: ['feeding', 'weight', 'litter'],
  },
  {
    key: 'bird', label: 'Птица', question: 'Как зовут вашу птицу?', icon: Bird, gradient: GRADIENT.bird,
    neutering: false, breedLabel: 'Вид', breedPlaceholder: 'Например, волнистый попугай',
    events: ['feeding', 'weight', 'defecation', 'eye_drops'],
  },
  {
    key: 'fish', label: 'Рыбка', question: 'Как зовут вашу рыбку?', icon: Fish, gradient: GRADIENT.fish,
    neutering: false, breedLabel: 'Вид', breedPlaceholder: 'Например, гуппи',
    events: ['feeding'],
  },
  {
    key: 'turtle', label: 'Черепаха', question: 'Как зовут вашу черепаху?', icon: Turtle, gradient: GRADIENT.reptile,
    neutering: false, breedLabel: 'Вид', breedPlaceholder: 'Например, красноухая',
    events: ['feeding', 'weight', 'defecation', 'eye_drops'],
  },
  {
    key: 'reptile', label: 'Ящерица или змея', question: 'Как зовут вашего питомца?', icon: PawPrint,
    gradient: GRADIENT.reptile, neutering: false, breedLabel: 'Вид', breedPlaceholder: 'Например, эублефар',
    events: ['feeding', 'weight', 'defecation'],
  },
  {
    key: 'other', label: 'Другой питомец', question: 'Как зовут вашего питомца?', icon: PawPrint,
    gradient: GRADIENT.default, neutering: true, breedLabel: 'Порода или вид', breedPlaceholder: 'Необязательно',
    events: ALL_EVENTS,
  },
];

const BY_KEY = new Map(SPECIES.map((s) => [s.key, s]));
const OTHER = BY_KEY.get('other')!;

/** Words that identify a species in text typed before species were keys
 *  («Кот», «кошка», «попугай»). */
const LEGACY_WORDS: [SpeciesKey, string[]][] = [
  ['cat', ['кот', 'кош']],
  ['dog', ['собак', 'пёс', 'пес', 'щен']],
  ['rabbit', ['крол']],
  ['ferret', ['хор']],
  ['guinea_pig', ['свинк']],
  ['chinchilla', ['шинш']],
  ['rat', ['крыс']],
  ['hamster', ['хомя']],
  ['bird', ['птиц', 'попуг', 'канар']],
  ['fish', ['рыб']],
  ['turtle', ['череп']],
  ['reptile', ['ящер', 'змея', 'геккон', 'игуан']],
];

/**
 * The species of a stored value: a key («cat»), or, for records typed in
 * by hand before the picker, a Russian word or English name. Anything
 * unrecognised is «Другой питомец», never nothing.
 */
export function getSpecies(value?: string | null): Species {
  if (!value) return OTHER;
  const v = value.trim().toLowerCase();
  const byKey = BY_KEY.get(v as SpeciesKey);
  if (byKey) return byKey;
  const byLabel = SPECIES.find((s) => s.label.toLowerCase() === v);
  if (byLabel) return byLabel;
  for (const [key, words] of LEGACY_WORDS) {
    if (words.some((w) => v.includes(w))) return BY_KEY.get(key)!;
  }
  return OTHER;
}

/** Human name for a stored species value (the value itself if it's free text we can't place). */
export function speciesLabel(value?: string | null): string {
  if (!value) return '';
  const species = getSpecies(value);
  return species.key === 'other' && !BY_KEY.has(value as SpeciesKey) ? value : species.label;
}

/** «Кастрация» for a male, «Стерилизация» for a female. */
export function neuteringLabel(gender?: string | null): string {
  if (gender === 'male' || gender === 'Мужской') return 'Кастрация';
  if (gender === 'female' || gender === 'Женский') return 'Стерилизация';
  return 'Кастрация или стерилизация';
}

/**
 * Tiles for a new pet: this species' builtin events shown, the other
 * builtins hidden. Custom event types and medications stay visible (an
 * absent key counts as shown, see TilesEditor), and everything can be
 * turned back on in the pet's settings.
 */
export function defaultTilesFor(value?: string | null): { order: string[]; visible: Record<string, boolean> } {
  const shown = new Set<string>(getSpecies(value).events);
  return {
    order: [],
    visible: Object.fromEntries(ALL_EVENTS.map((key) => [key, shown.has(key)])),
  };
}

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

/** The built-in event types (web/builtin_event_types.py). */
export type BuiltinEvent =
  | 'feeding' | 'weight' | 'defecation' | 'litter' | 'asthma' | 'eye_drops' | 'ear_cleaning' | 'tooth_brushing'
  | 'treat' | 'water_intake' | 'appetite' | 'urination' | 'vomiting' | 'temperature' | 'mood' | 'cough' | 'seizure'
  | 'itching' | 'limping' | 'bathing' | 'brushing' | 'nail_trim' | 'walk' | 'play' | 'training' | 'cage_cleaning'
  | 'water_change' | 'filter_cleaning' | 'uv_lamp' | 'misting' | 'shedding' | 'water_test' | 'terrarium_climate' | 'out_of_cage';

/** The original eight: they were all a pet's, hidden or shown; the catalogue has since grown (see tilesConfig). */
const ORIGINAL: BuiltinEvent[] = ['feeding', 'weight', 'defecation', 'litter', 'asthma', 'eye_drops', 'ear_cleaning', 'tooth_brushing'];

/**
 * What a new pet starts with: a handful that matter from the first day, in the order they are most often needed, so that the
 * «+» is not a wall on the first look. Everything else is one tap away in the pet's events («Добавить событие»), where the
 * ones that suit its kind of animal come first (SUGGESTED).
 */
const STARTER: Record<SpeciesKey, BuiltinEvent[]> = {
  cat: ['feeding', 'weight', 'litter', 'vomiting', 'brushing'],
  dog: ['feeding', 'weight', 'walk', 'defecation', 'vomiting'],
  // Not eating is an emergency for a rabbit: appetite is on from the first day.
  rabbit: ['feeding', 'weight', 'defecation', 'appetite', 'cage_cleaning'],
  ferret: ['feeding', 'weight', 'litter', 'play'],
  guinea_pig: ['feeding', 'weight', 'defecation', 'cage_cleaning'],
  chinchilla: ['feeding', 'weight', 'cage_cleaning', 'bathing'],
  rat: ['feeding', 'weight', 'cage_cleaning', 'play'],
  hamster: ['feeding', 'weight', 'cage_cleaning'],
  bird: ['feeding', 'weight', 'cage_cleaning', 'bathing', 'out_of_cage'],
  // The water is what an aquarium's care is about: its numbers, not a weight.
  fish: ['feeding', 'water_test', 'water_change', 'filter_cleaning'],
  turtle: ['feeding', 'weight', 'terrarium_climate', 'water_change', 'uv_lamp'],
  reptile: ['feeding', 'weight', 'shedding', 'terrarium_climate', 'misting'],
  // Not every animal has a cage: nothing about one here, it is in the catalogue for whoever has.
  other: ['feeding', 'weight', 'defecation'],
};

/** Beyond the starter set, what is worth offering first for this kind of animal. */
const SUGGESTED: Record<SpeciesKey, BuiltinEvent[]> = {
  cat: ['water_intake', 'defecation', 'urination', 'appetite', 'temperature', 'mood', 'cough', 'itching', 'nail_trim', 'bathing', 'play', 'treat', 'eye_drops', 'ear_cleaning', 'tooth_brushing', 'asthma', 'seizure'],
  dog: ['water_intake', 'urination', 'appetite', 'temperature', 'mood', 'cough', 'itching', 'limping', 'bathing', 'brushing', 'nail_trim', 'training', 'play', 'treat', 'eye_drops', 'ear_cleaning', 'tooth_brushing', 'seizure'],
  rabbit: ['water_intake', 'urination', 'temperature', 'mood', 'litter', 'nail_trim', 'brushing', 'treat', 'eye_drops', 'ear_cleaning', 'out_of_cage', 'play'],
  ferret: ['defecation', 'appetite', 'temperature', 'mood', 'bathing', 'nail_trim', 'treat', 'ear_cleaning', 'cage_cleaning', 'out_of_cage'],
  guinea_pig: ['water_intake', 'appetite', 'litter', 'temperature', 'mood', 'nail_trim', 'treat', 'eye_drops', 'out_of_cage'],
  chinchilla: ['water_intake', 'appetite', 'defecation', 'mood', 'nail_trim', 'treat', 'out_of_cage'],
  rat: ['water_intake', 'appetite', 'defecation', 'temperature', 'mood', 'treat', 'bathing', 'cough', 'out_of_cage'],
  hamster: ['water_intake', 'appetite', 'defecation', 'mood', 'play', 'treat'],
  bird: ['shedding', 'defecation', 'appetite', 'water_intake', 'mood', 'nail_trim', 'treat', 'misting'],
  fish: ['water_intake', 'mood', 'treat', 'cage_cleaning'],
  turtle: ['cage_cleaning', 'filter_cleaning', 'defecation', 'appetite', 'bathing', 'shedding', 'misting', 'mood'],
  reptile: ['cage_cleaning', 'defecation', 'appetite', 'water_intake', 'bathing', 'uv_lamp', 'water_change', 'mood'],
  other: ['water_intake', 'appetite', 'urination', 'temperature', 'mood', 'cage_cleaning', 'bathing', 'brushing', 'treat', 'play'],
};

export interface Species {
  key: SpeciesKey;
  label: string;
  /** «для собаки»: the name after «для», where the nominative reads wrongly. */
  forWhom: string;
  /** Onboarding's name question: «Как зовут вашего кота?» */
  question: string;
  icon: LucideIcon;
  gradient: string;
  /** Castration/sterilisation is a thing for mammals, not for birds, fish or reptiles. */
  neutering: boolean;
  /** What «Порода» is called: fish and reptiles have species, not breeds. */
  breedLabel: string;
  breedPlaceholder: string;
  /** The few built-in events a new pet of this species starts with, in order. */
  events: BuiltinEvent[];
  /** More that suit it, offered first when adding an event. */
  suggested: BuiltinEvent[];
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
    key: 'cat', label: 'Кот', forWhom: 'кота', question: 'Как зовут вашего кота?', icon: Cat, gradient: GRADIENT.cat,
    neutering: true, breedLabel: 'Порода', breedPlaceholder: 'Например, британская',
    events: STARTER.cat,
    suggested: SUGGESTED.cat,
  },
  {
    key: 'dog', label: 'Собака', forWhom: 'собаки', question: 'Как зовут вашу собаку?', icon: Dog, gradient: GRADIENT.dog,
    neutering: true, breedLabel: 'Порода', breedPlaceholder: 'Например, лабрадор',
    events: STARTER.dog,
    suggested: SUGGESTED.dog,
  },
  {
    key: 'rabbit', label: 'Кролик', forWhom: 'кролика', question: 'Как зовут вашего кролика?', icon: Rabbit, gradient: GRADIENT.rabbit,
    neutering: true, breedLabel: 'Порода', breedPlaceholder: 'Например, карликовый',
    events: STARTER.rabbit,
    suggested: SUGGESTED.rabbit,
  },
  {
    key: 'ferret', label: 'Хорёк', forWhom: 'хорька', question: 'Как зовут вашего хорька?', icon: PawPrint, gradient: GRADIENT.small,
    neutering: true, breedLabel: 'Окрас', breedPlaceholder: 'Например, соболиный',
    events: STARTER.ferret,
    suggested: SUGGESTED.ferret,
  },
  {
    key: 'guinea_pig', label: 'Морская свинка', forWhom: 'морской свинки', question: 'Как зовут вашу морскую свинку?', icon: PawPrint,
    gradient: GRADIENT.small, neutering: true, breedLabel: 'Порода', breedPlaceholder: 'Например, абиссинская',
    events: STARTER.guinea_pig,
    suggested: SUGGESTED.guinea_pig,
  },
  {
    key: 'chinchilla', label: 'Шиншилла', forWhom: 'шиншиллы', question: 'Как зовут вашу шиншиллу?', icon: Squirrel,
    gradient: GRADIENT.small, neutering: true, breedLabel: 'Окрас', breedPlaceholder: 'Например, стандартный серый',
    events: STARTER.chinchilla,
    suggested: SUGGESTED.chinchilla,
  },
  {
    key: 'rat', label: 'Крыса', forWhom: 'крысы', question: 'Как зовут вашу крысу?', icon: Rat, gradient: GRADIENT.small,
    neutering: true, breedLabel: 'Порода', breedPlaceholder: 'Например, дамбо',
    events: STARTER.rat,
    suggested: SUGGESTED.rat,
  },
  {
    key: 'hamster', label: 'Хомяк', forWhom: 'хомяка', question: 'Как зовут вашего хомяка?', icon: Squirrel, gradient: GRADIENT.small,
    neutering: true, breedLabel: 'Порода', breedPlaceholder: 'Например, джунгарский',
    events: STARTER.hamster,
    suggested: SUGGESTED.hamster,
  },
  {
    key: 'bird', label: 'Птица', forWhom: 'птицы', question: 'Как зовут вашу птицу?', icon: Bird, gradient: GRADIENT.bird,
    neutering: false, breedLabel: 'Вид', breedPlaceholder: 'Например, волнистый попугай',
    events: STARTER.bird,
    suggested: SUGGESTED.bird,
  },
  {
    key: 'fish', label: 'Рыбка', forWhom: 'рыбки', question: 'Как зовут вашу рыбку?', icon: Fish, gradient: GRADIENT.fish,
    neutering: false, breedLabel: 'Вид', breedPlaceholder: 'Например, гуппи',
    events: STARTER.fish,
    suggested: SUGGESTED.fish,
  },
  {
    key: 'turtle', label: 'Черепаха', forWhom: 'черепахи', question: 'Как зовут вашу черепаху?', icon: Turtle, gradient: GRADIENT.reptile,
    neutering: false, breedLabel: 'Вид', breedPlaceholder: 'Например, красноухая',
    events: STARTER.turtle,
    suggested: SUGGESTED.turtle,
  },
  {
    key: 'reptile', label: 'Ящерица или змея', forWhom: 'ящерицы или змеи', question: 'Как зовут вашего питомца?', icon: PawPrint,
    gradient: GRADIENT.reptile, neutering: false, breedLabel: 'Вид', breedPlaceholder: 'Например, эублефар',
    events: STARTER.reptile,
    suggested: SUGGESTED.reptile,
  },
  {
    key: 'other', label: 'Другой питомец', forWhom: 'питомца', question: 'Как зовут вашего питомца?', icon: PawPrint,
    gradient: GRADIENT.default, neutering: true, breedLabel: 'Порода или вид', breedPlaceholder: 'Необязательно',
    events: STARTER.other,
    suggested: SUGGESTED.other,
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
 * Tiles for a new pet: the few built-in events that suit its species, in order. Of the original eight, those not in the set
 * are said to be hidden (an unsaid one counts as shown, see tilesConfig); a type added to the catalogue since is hidden
 * unless said otherwise. Custom event types and medications stay shown, and everything can be changed in the pet's events.
 */
export function defaultTilesFor(value?: string | null): { order: string[]; visible: Record<string, boolean> } {
  const starter = getSpecies(value).events;
  const shown = new Set<string>(starter);
  return {
    order: [...starter],
    visible: Object.fromEntries([...ORIGINAL, ...starter].map((key) => [key, shown.has(key)])),
  };
}

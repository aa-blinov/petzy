// Color constants for tiles
export const TILE_COLORS = {
  brown: 'brown',
  orange: 'orange',
  red: 'red',
  green: 'green',
  purple: 'purple',
  teal: 'teal',
  cyan: 'cyan',
  yellow: 'yellow',
  blue: 'blue',
  pink: 'pink',
  gray: 'gray',
} as const;

export type TileColor = typeof TILE_COLORS[keyof typeof TILE_COLORS];

/** Russian names for the stored species keys. */
export const SPECIES_LABELS: Record<string, string> = {
  cat: 'Кот',
  dog: 'Собака',
  bird: 'Птица',
  fish: 'Рыба',
  other: 'Другое',
};

/** Spoken names for the colour swatches: the keys are English, and a
 *  Russian screen reader read "teal" or "cyan" out as gibberish. */
export const TILE_COLOR_LABELS: Record<TileColor, string> = {
  brown: 'Коричневый',
  orange: 'Оранжевый',
  red: 'Красный',
  green: 'Зелёный',
  purple: 'Фиолетовый',
  teal: 'Бирюзовый',
  cyan: 'Голубой',
  yellow: 'Жёлтый',
  blue: 'Синий',
  pink: 'Розовый',
  gray: 'Серый',
};

/** Maps a tile's color id to its pastel CSS custom-property. */
export const pastelColorMap: Record<string, string> = {
  brown: 'var(--tile-brown)',
  orange: 'var(--tile-orange)',
  red: 'var(--tile-red)',
  green: 'var(--tile-green)',
  purple: 'var(--tile-purple)',
  teal: 'var(--tile-teal)',
  cyan: 'var(--tile-cyan)',
  yellow: 'var(--tile-yellow)',
  blue: 'var(--tile-blue)',
  pink: 'var(--tile-pink)',
  gray: 'var(--tile-gray)',
};

import {
  Footprints,
  Cat,
  Dog,
  Bird,
  Rabbit,
  Fish,
  type LucideIcon,
} from 'lucide-react';

/** Pet gender — the stored value and the label shown for it.
 *
 *  "Мальчик"/"Девочка" rather than "Мужской"/"Женский": this is a pet
 *  diary, and that is how owners talk about their animals. */
export const GENDER_OPTIONS = [
  { label: 'Не указан', value: '' },
  { label: 'Мальчик', value: 'male' },
  { label: 'Девочка', value: 'female' },
];

/** Legacy spellings that predate the codes above, kept so older records
 *  read the same as new ones instead of showing their stored text. */
const LEGACY_GENDER_LABELS: Record<string, string> = {
  'Мужской': 'Мальчик',
  'Женский': 'Девочка',
};

/**
 * Human-readable gender for display.
 *
 * The form stores a code (`male`/`female`) while the pet card and the
 * pets list used to print `pet.gender` straight out of the record — so a
 * pet added through the UI showed a bare "male". Unknown values pass
 * through unchanged, which keeps anything hand-entered readable.
 */
export function genderLabel(value?: string | null): string {
  if (!value) return '';
  const known = GENDER_OPTIONS.find(o => o.value === value);
  if (known) return known.label;
  return LEGACY_GENDER_LABELS[value] ?? value;
}

/** Species icon (lucide) for the PetSummaryCard hero fallback. */
export const speciesIconMap: Record<string, LucideIcon> = {
  cat: Cat,
  dog: Dog,
  bird: Bird,
  rabbit: Rabbit,
  fish: Fish,
  // hamster, reptile and other species fall back to Footprints below.
};

/** Generic species icon used when the species isn't recognized. */
export const SPECIES_FALLBACK_ICON: LucideIcon = Footprints;

/**
 * Photo-placeholder gradient (see --species-gradient-* in globals.css)
 * for the pet's no-photo tile — keyed the same as speciesIconMap so a
 * cat's empty tile reads differently from a fish's at a glance, not just
 * by icon shape.
 */
export const speciesGradientMap: Record<string, string> = {
  cat: 'var(--species-gradient-cat)',
  dog: 'var(--species-gradient-dog)',
  bird: 'var(--species-gradient-bird)',
  rabbit: 'var(--species-gradient-rabbit)',
  fish: 'var(--species-gradient-fish)',
};

/** Fallback gradient for an unset or unrecognized species. */
export const SPECIES_GRADIENT_FALLBACK = 'var(--species-gradient-default)';


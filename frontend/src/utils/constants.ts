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
} as const;

// Health record types
export const HEALTH_RECORD_TYPES = {
  feeding: 'feeding',
  weight: 'weight',
  asthma: 'asthma',
  defecation: 'defecation',
  litter: 'litter',
  eye_drops: 'eye_drops',
  tooth_brushing: 'tooth_brushing',
  ear_cleaning: 'ear_cleaning',
  medications: 'medications',
} as const;

export type TileColor = typeof TILE_COLORS[keyof typeof TILE_COLORS];
export type HealthRecordType = typeof HEALTH_RECORD_TYPES[keyof typeof HEALTH_RECORD_TYPES];

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
};

import {
  Utensils,
  Scale,
  Wind,
  Toilet,
  Shovel,
  Eye,
  Toothbrush,
  Ear,
  Pill,
  Footprints,
  Cat,
  Dog,
  Bird,
  Rabbit,
  Fish,
  type LucideIcon,
} from 'lucide-react';

/** Category icon (lucide) for each health-record type. Rendered inside
 *  HistoryItem's pill-icon and inside QuickAddSheet tiles. */
export const typeIconMap: Record<string, LucideIcon> = {
  feeding: Utensils,
  weight: Scale,
  // No lungs glyph in lucide; wind is the closest read for "breathing".
  asthma: Wind,
  // Was Droplet, which reads as liquid — urine, water, a spill — rather
  // than stool. Toilet names the event without being crude.
  defecation: Toilet,
  // Was Brush, i.e. grooming or painting. Changing a tray is scooping it.
  litter: Shovel,
  // Organ icons for the two body-part routines: at a glance in a mixed
  // list, "eye thing" and "ear thing" are read faster than the implements
  // (a pipette and a cleaning brush) would be.
  eye_drops: Eye,
  ear_cleaning: Ear,
  // Was Sparkles, which says "clean/shiny" generically — it could have
  // been grooming, a wash, anything.
  tooth_brushing: Toothbrush,
  medications: Pill,
};

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


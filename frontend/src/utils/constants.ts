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


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


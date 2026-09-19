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

/** Category emoji for each health-record type, used inside HistoryItem's
 *  pill-icon. Kept here so dashboard, history, and quick-add stay in sync. */
export const typeIconMap: Record<string, string> = {
  feeding: '🍽️',
  weight: '⚖️',
  asthma: '💨',
  defecation: '💩',
  litter: '🧹',
  eye_drops: '👁️',
  tooth_brushing: '🦷',
  ear_cleaning: '👂',
  medications: '💊',
};


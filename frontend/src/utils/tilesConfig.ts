import type { TileColor } from './constants';
import type { EventType } from '../services/eventTypes.service';

export interface TileConfig {
  id: string;
  title: string;
  color: TileColor;
  isTile?: boolean; // If false, won't show on Dashboard grid, QuickAddSheet or in Tiles Settings
}

/** The one tile not driven by the event-type registry — medications have
 *  their own domain (courses, doses, inventory), not a generic event. */
export const MEDICATIONS_TILE: TileConfig = {
  id: 'medications',
  title: 'Лекарства',
  color: 'purple',
  isTile: false,
};

/** Every quick-add tile: one per registered event type, plus medications.
 *  The registry is already sorted builtin-first then alphabetically, so
 *  this needs no further default ordering — `tiles_settings.order` (per
 *  pet) is what actually reorders/hides them at render time. */
export function buildTiles(eventTypes: EventType[]): TileConfig[] {
  return [
    ...eventTypes.map((t): TileConfig => ({ id: t.key, title: t.label, color: t.color })),
    MEDICATIONS_TILE,
  ];
}

/** The catalogue's groups, in the order they are listed. A type says which it is in (`category`); the family's own are «Свои». */
export const EVENT_CATEGORIES = [
  { key: 'food', label: 'Питание и вода' },
  { key: 'excretion', label: 'Туалет' },
  { key: 'health', label: 'Самочувствие и здоровье' },
  { key: 'care', label: 'Уход' },
  { key: 'activity', label: 'Активность' },
  { key: 'habitat', label: 'Среда обитания' },
  { key: 'custom', label: 'Свои' },
] as const;

/** The eight types every pet has always had on its «+». Anything added to the catalogue later is offered, not shown. */
export const ORIGINAL_EVENTS = ['feeding', 'weight', 'defecation', 'litter', 'asthma', 'eye_drops', 'ear_cleaning', 'tooth_brushing'] as const;

export interface TilesSettings {
  order: string[];
  visible: Record<string, boolean>;
}

/** Absent from `order` sorts last, absent from `visible` counts as shown
 *  (see TilesEditor) — so an empty default is enough: a pet with no saved
 *  preference just shows every tile in the registry's own order. */
export const DEFAULT_TILES_SETTINGS: TilesSettings = { order: [], visible: {} };

const SHOWN_UNLESS_SAID = new Set<string>(ORIGINAL_EVENTS);

/**
 * Whether a type is on this pet's «+». Said either way in `visible`, that is the answer. Never said: the original eight, the
 * family's own types and medications have always been shown; a type added to the catalogue since is not, or every pet's «+»
 * would fill with dozens of buttons it never asked for.
 */
export function isTileShown(settings: TilesSettings, id: string): boolean {
  const said = settings.visible[id];
  if (said !== undefined) return said;
  return SHOWN_UNLESS_SAID.has(id) || id.startsWith('custom_') || id === 'medications';
}

/** The ids by the order the pet chose; one it never placed comes after those it did. */
export function byTileOrder<T extends { id: string }>(items: T[], settings: TilesSettings): T[] {
  const rank = (id: string) => {
    const at = settings.order.indexOf(id);
    return at === -1 ? Number.MAX_SAFE_INTEGER : at;
  };
  return [...items].sort((a, b) => rank(a.id) - rank(b.id));
}

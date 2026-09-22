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
  title: 'Препараты',
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

export interface TilesSettings {
  order: string[];
  visible: Record<string, boolean>;
}

/** Absent from `order` sorts last, absent from `visible` counts as shown
 *  (see TilesEditor) — so an empty default is enough: a pet with no saved
 *  preference just shows every tile in the registry's own order. */
export const DEFAULT_TILES_SETTINGS: TilesSettings = { order: [], visible: {} };

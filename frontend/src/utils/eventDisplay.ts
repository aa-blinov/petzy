/**
 * Turns an event-type registry entry into the small "how to show this in
 * a list" bundle History/Dashboard/HistoryItem need — replaces the old
 * historyConfig.ts, which hand-wrote one renderDetails per builtin type.
 *
 * Medications aren't part of the registry (their own domain — courses,
 * doses, inventory), so they keep a static entry here.
 */
import type { LucideIcon } from 'lucide-react';
import type { TileColor } from './constants';
import type { EventType } from '../services/eventTypes.service';
import { getEventIcon } from './iconRegistry';

export interface HistoryItem {
  _id: string;
  date_time: string;
  username?: string;
  [key: string]: unknown;
}

export interface EventDisplayConfig {
  displayName: string;
  color: TileColor;
  icon: LucideIcon;
  renderDetails: (item: HistoryItem) => string;
}

function renderMedicationDetails(item: HistoryItem): string {
  let html = `<span><strong>Препарат:</strong> ${item.medication_name || 'Неизвестно'}</span>`;
  html += `<span><strong>Доза:</strong> ${item.dose_taken}</span>`;
  if (item.comment && item.comment !== '-') {
    html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
  }
  return html;
}

export const MEDICATIONS_DISPLAY: EventDisplayConfig = {
  displayName: 'Препараты',
  color: 'purple',
  icon: getEventIcon('pill'),
  renderDetails: renderMedicationDetails,
};

/** Render an event's field values generically, in declaration order —
 *  a select field shows its option's text, not the raw stored value. */
export function renderEventDetails(item: HistoryItem, eventType: EventType): string {
  const fields = (item.fields as Record<string, unknown>) ?? {};
  let html = '';
  for (const field of eventType.fields) {
    const raw = fields[field.name];
    if (raw === undefined || raw === null || raw === '') continue;

    let display = String(raw);
    if (field.type === 'select') {
      const option = field.options?.find((opt) => opt.value === String(raw));
      if (option) display = option.text;
    }
    html += `<span><strong>${field.label}:</strong> ${display}</span>`;
  }
  if (item.comment && item.comment !== '-') {
    html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
  }
  return html;
}

export function buildEventDisplayConfig(eventType: EventType): EventDisplayConfig {
  return {
    displayName: eventType.label,
    color: eventType.color,
    icon: getEventIcon(eventType.icon),
    renderDetails: (item) => renderEventDetails(item, eventType),
  };
}

/** One map covering every registered type plus medications — the single
 *  source History/Dashboard/HistoryItem look up `record_type` against. */
export function buildEventDisplayConfigs(eventTypes: EventType[]): Record<string, EventDisplayConfig> {
  const map: Record<string, EventDisplayConfig> = { medications: MEDICATIONS_DISPLAY };
  for (const eventType of eventTypes) {
    map[eventType.key] = buildEventDisplayConfig(eventType);
  }
  return map;
}

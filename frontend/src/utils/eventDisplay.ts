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
  /** Label/value pairs shown under the record, rendered as text.
      This used to build an HTML string for dangerouslySetInnerHTML with
      the raw comment, field values, field labels and medication name
      interpolated in: anyone a pet was shared with could plant markup
      (a script included) that ran in the other owner's app. */
  details: (item: HistoryItem) => DetailLine[];
}

export interface DetailLine {
  label: string;
  value: string;
}

function commentLine(item: HistoryItem): DetailLine[] {
  return item.comment && item.comment !== '-' ? [{ label: 'Комментарий', value: String(item.comment) }] : [];
}

function medicationDetails(item: HistoryItem): DetailLine[] {
  return [
    { label: 'Препарат', value: String(item.medication_name || 'Неизвестно') },
    { label: 'Доза', value: String(item.dose_taken) },
    ...commentLine(item),
  ];
}

export const MEDICATIONS_DISPLAY: EventDisplayConfig = {
  displayName: 'Препараты',
  color: 'purple',
  icon: getEventIcon('pill'),
  details: medicationDetails,
};

/** Render an event's field values generically, in declaration order —
 *  a select field shows its option's text, not the raw stored value. */
export function eventDetails(item: HistoryItem, eventType: EventType): DetailLine[] {
  const fields = (item.fields as Record<string, unknown>) ?? {};
  const lines: DetailLine[] = [];
  for (const field of eventType.fields) {
    const raw = fields[field.name];
    if (raw === undefined || raw === null || raw === '') continue;

    let display = String(raw);
    if (field.type === 'select') {
      const option = field.options?.find((opt) => opt.value === String(raw));
      if (option) display = option.text;
    }
    lines.push({ label: field.label, value: display });
  }
  return [...lines, ...commentLine(item)];
}

export function buildEventDisplayConfig(eventType: EventType): EventDisplayConfig {
  return {
    displayName: eventType.label,
    color: eventType.color,
    icon: getEventIcon(eventType.icon),
    details: (item) => eventDetails(item, eventType),
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

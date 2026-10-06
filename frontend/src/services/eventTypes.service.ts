import api from './api';
import type { TileColor } from '../utils/constants';

export interface EventFieldOption {
  value: string;
  text: string;
}

export interface EventTypeField {
  name: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'textarea';
  required: boolean;
  options?: EventFieldOption[];
  /** Only meaningful for type: 'number'. */
  min?: number | null;
  max?: number | null;
  step?: number | null;
}

export interface EventTypeChart {
  kind: 'count' | 'value';
  value_field?: string | null;
  value_label?: string | null;
}

export interface EventType {
  key: string;
  label: string;
  icon: string;
  color: TileColor;
  is_builtin: boolean;
  /** Where a built-in type belongs in the catalogue (food, health, care...); none for the family's own. */
  category?: string | null;
  /** Who made a custom type; a household sees one another's. */
  created_by?: string | null;
  fields: EventTypeField[];
  chart: EventTypeChart;
}

export interface EventTypeInput {
  label: string;
  icon: string;
  color: string;
  fields: EventTypeField[];
  chart: EventTypeChart;
}

export const eventTypesService = {
  async list(): Promise<EventType[]> {
    const response = await api.get<{ event_types: EventType[] }>('/event-types');
    return response.data.event_types;
  },

  /** The types a pet has at least one record of: what a filter of its history has something to show for. */
  async usedBy(petId: string): Promise<string[]> {
    const response = await api.get<{ types: string[] }>('/events/used-types', { params: { pet_id: petId } });
    return response.data.types;
  },

  async create(data: EventTypeInput): Promise<EventType> {
    const response = await api.post<EventType>('/event-types', data);
    return response.data;
  },

  async update(key: string, data: Partial<EventTypeInput>): Promise<EventType> {
    const response = await api.put<EventType>(`/event-types/${key}`, data);
    return response.data;
  },

  /** ``withEvents``: the type goes together with its records (asked after the server says how many there are). */
  async remove(key: string, withEvents = false): Promise<void> {
    await api.delete(`/event-types/${key}`, { params: withEvents ? { with_events: 'true' } : undefined });
  },

  /** How many records the type has, without deleting anything: the question about removing a type is asked with
   *  the number in it, not asked twice. */
  async eventsCount(key: string): Promise<number> {
    const response = await api.delete<{ events_count: number }>(`/event-types/${key}`, { params: { preview: 'true' } });
    return response.data.events_count ?? 0;
  },
};

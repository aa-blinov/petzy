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

  async create(data: EventTypeInput): Promise<EventType> {
    const response = await api.post<EventType>('/event-types', data);
    return response.data;
  },

  async update(key: string, data: Partial<EventTypeInput>): Promise<EventType> {
    const response = await api.put<EventType>(`/event-types/${key}`, data);
    return response.data;
  },

  async remove(key: string): Promise<void> {
    await api.delete(`/event-types/${key}`);
  },
};

import api from './api';

export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface HealthRecord {
  _id: string;
  pet_id: string;
  type?: string;
  date_time: string;
  username?: string;
  record_type?: string;
  medication_name?: string;
  comment?: string;
  fields: Record<string, unknown>;
  [key: string]: unknown;
}

export type TimelineResponse = PaginatedResponse<HealthRecord>;
export type EventListResponse = PaginatedResponse<HealthRecord>;

export interface EventCreate {
  pet_id: string;
  date: string;
  time: string;
  comment?: string;
  fields: Record<string, unknown>;
}

export interface EventUpdate {
  date?: string;
  time?: string;
  comment?: string;
  fields?: Record<string, unknown>;
}

/** CRUD against the generic /api/events endpoint. `type` is an event-type
 *  registry key (a builtin one or a custom one) — the API doesn't special-
 *  case it. Medications go through their own service instead. */
export const healthRecordsService = {
  async create(type: string, data: EventCreate): Promise<{ message: string }> {
    const response = await api.post<{ message: string }>('/events', { ...data, type });
    return response.data;
  },

  async getList(type: string, petId: string, page: number = 1, pageSize: number = 100): Promise<EventListResponse> {
    const response = await api.get<EventListResponse>('/events', {
      params: { pet_id: petId, type, page, page_size: pageSize },
    });
    return response.data;
  },

  async get(recordId: string): Promise<HealthRecord> {
    const response = await api.get<HealthRecord>(`/events/${recordId}`);
    return response.data;
  },

  async update(recordId: string, data: EventUpdate): Promise<{ message: string }> {
    const response = await api.put<{ message: string }>(`/events/${recordId}`, data);
    return response.data;
  },

  async delete(recordId: string): Promise<void> {
    await api.delete(`/events/${recordId}`);
  },

  async getStats(
    type: string,
    petId: string,
    days: number = 30
  ): Promise<{ data: { date: string; value: number | string }[] }> {
    const response = await api.get<{ data: { date: string; value: number | string }[] }>(`/stats/health`, {
      params: { pet_id: petId, type, days }
    });
    return response.data;
  },

  async getTimeline(
    petId: string,
    page: number = 1,
    pageSize: number = 100,
    type: string = 'all'
  ): Promise<TimelineResponse> {
    const response = await api.get<TimelineResponse>('/history/timeline', {
      params: { pet_id: petId, page, page_size: pageSize, type }
    });
    return response.data;
  }
};

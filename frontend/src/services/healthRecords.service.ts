import api from './api';
import type { HealthRecordType } from '../utils/constants';

export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface HealthRecord {
  _id: string;
  pet_id: string;
  date_time: string;
  username?: string;
  [key: string]: any;
}

export interface HealthRecordCreate {
  pet_id: string;
  date: string;
  time: string;
  [key: string]: any;
}

export interface HealthRecordUpdate {
  date?: string;
  time?: string;
  [key: string]: any;
}

// Type-specific list responses
export interface FeedingListResponse {
  feedings: HealthRecord[];
  page: number;
  page_size: number;
  total: number;
}

export interface AsthmaListResponse {
  attacks: HealthRecord[];
  page: number;
  page_size: number;
  total: number;
}

export interface DefecationListResponse {
  defecations: HealthRecord[];
  page: number;
  page_size: number;
  total: number;
}

export interface LitterListResponse {
  litter_changes: HealthRecord[];
  page: number;
  page_size: number;
  total: number;
}

export interface WeightListResponse {
  weights: HealthRecord[];
  page: number;
  page_size: number;
  total: number;
}

export interface EyeDropsListResponse {
  eye_drops: HealthRecord[];
  page: number;
  page_size: number;
  total: number;
}

export interface ToothBrushingListResponse {
  tooth_brushing: HealthRecord[];
  page: number;
  page_size: number;
  total: number;
}

export interface EarCleaningListResponse {
  ear_cleaning: HealthRecord[];
  page: number;
  page_size: number;
  total: number;
}

type ListResponseMap = {
  feeding: FeedingListResponse;
  asthma: AsthmaListResponse;
  defecation: DefecationListResponse;
  litter: LitterListResponse;
  weight: WeightListResponse;
  eye_drops: EyeDropsListResponse;
  tooth_brushing: ToothBrushingListResponse;
  ear_cleaning: EarCleaningListResponse;
};

export const healthRecordsService = {
  async create<T extends HealthRecordType>(
    type: T,
    data: HealthRecordCreate
  ): Promise<HealthRecord> {
    await api.post<{ message: string }>(`/${type}`, data);
    // The API returns just a message, so we need to fetch the created record
    // For now, return a placeholder - in real implementation, the API might return the record
    return {} as HealthRecord;
  },

  async getList<T extends HealthRecordType>(
    type: T,
    petId: string,
    page: number = 1,
    pageSize: number = 100
  ): Promise<ListResponseMap[T]> {
    const response = await api.get<ListResponseMap[T]>(`/${type}`, {
      params: { pet_id: petId, page, page_size: pageSize }
    });
    return response.data;
  },

  async get<T extends HealthRecordType>(
    type: T,
    recordId: string
  ): Promise<HealthRecord> {
    const response = await api.get<HealthRecord>(`/${type}/${recordId}`);
    return response.data;
  },

  async update<T extends HealthRecordType>(
    type: T,
    recordId: string,
    data: HealthRecordUpdate
  ): Promise<HealthRecord> {
    await api.put<{ message: string }>(`/${type}/${recordId}`, data);
    // Similar to create, might need to fetch updated record
    return {} as HealthRecord;
  },

  async delete<T extends HealthRecordType>(
    type: T,
    recordId: string
  ): Promise<void> {
    await api.delete(`/${type}/${recordId}`);
  },

  async getStats(
    type: string,
    petId: string,
    days: number = 30
  ): Promise<{ data: { date: string; value: any }[] }> {
    const response = await api.get<{ data: { date: string; value: any }[] }>(`/stats/health`, {
      params: { pet_id: petId, type, days }
    });
    return response.data;
  }
};


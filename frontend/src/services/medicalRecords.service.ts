import api from './api';
import { deviceTimeZone } from '../utils/timezone';

export type MedicalKind = 'vaccination' | 'parasite' | 'visit' | 'procedure';
export type ParasiteTarget = 'fleas_ticks' | 'worms' | 'both';

export const MEDICAL_KIND_LABELS: Record<MedicalKind, { section: string; one: string; titleLabel: string; titlePlaceholder: string }> = {
  vaccination: { section: 'Прививки', one: 'Прививка', titleLabel: 'Название вакцины', titlePlaceholder: 'Например, Нобивак Tricat Trio' },
  parasite: { section: 'Обработки от паразитов', one: 'Обработка от паразитов', titleLabel: 'Препарат', titlePlaceholder: 'Например, Дронтал Плюс' },
  visit: { section: 'Визиты и диагнозы', one: 'Визит к врачу', titleLabel: 'Повод визита', titlePlaceholder: 'Например, плановый осмотр' },
  procedure: { section: 'Операции и процедуры', one: 'Операция или процедура', titleLabel: 'Название', titlePlaceholder: 'Например, чистка зубов' },
};

export const PARASITE_TARGET_LABELS: Record<ParasiteTarget, string> = {
  fleas_ticks: 'Блохи и клещи',
  worms: 'Глисты',
  both: 'Всё сразу',
};

export interface MedicalRecord {
  _id: string;
  pet_id: string;
  kind: MedicalKind;
  /** YYYY-MM-DD, no time. */
  date: string;
  title: string;
  next_due: string | null;
  /** overdue, soon, ok; none when no repeat is due or a newer record replaced this one. */
  status: 'overdue' | 'soon' | 'ok' | 'none';
  days_left: number | null;
  superseded: boolean;
  clinic: string | null;
  vet: string | null;
  note: string | null;
  batch: string | null;
  target: ParasiteTarget | null;
  complaint: string | null;
  diagnosis: string | null;
  recommendations: string | null;
  documents: { id: string; title: string }[];
}

export interface MedicalRecordInput {
  date: string;
  title: string;
  next_due: string | null;
  clinic: string | null;
  vet: string | null;
  note: string | null;
  batch: string | null;
  target: ParasiteTarget | null;
  complaint: string | null;
  diagnosis: string | null;
  recommendations: string | null;
  document_ids: string[];
}

export const medicalRecordsService = {
  async get(id: string): Promise<MedicalRecord> {
    const response = await api.get<{ record: MedicalRecord }>(`/medical-records/${id}`, { params: { tz: deviceTimeZone() } });
    return response.data.record;
  },

  /** Every record of a kind (the card shows the latest ten), newest first. */
  async list(petId: string, kind: MedicalKind): Promise<MedicalRecord[]> {
    const response = await api.get<{ records: MedicalRecord[] }>('/medical-records', { params: { pet_id: petId, kind, tz: deviceTimeZone() } });
    return response.data.records;
  },

  async create(petId: string, kind: MedicalKind, data: MedicalRecordInput): Promise<string> {
    const response = await api.post<{ id: string }>('/medical-records', { ...data, pet_id: petId, kind });
    return response.data.id;
  },

  async update(id: string, data: MedicalRecordInput): Promise<void> {
    await api.put(`/medical-records/${id}`, data);
  },
};

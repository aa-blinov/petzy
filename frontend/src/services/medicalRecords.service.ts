import api from './api';
import { idempotencyHeaders } from '../utils/idempotency';
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
  /** What a vaccination is against (a key of the vaccine catalogue); an old entry's is read from its name. */
  protects: string | null;
  protects_label: string | null;
  complaint: string | null;
  diagnosis: string | null;
  recommendations: string | null;
  /** The weighing in the feed that was said at this visit (a visit's only). */
  weight_event_id?: string | null;
  documents: { id: string; title: string }[];
  /** The version of the record (what `base_version` of an edit names); only the record's own routes bring it. */
  updated_at?: string | null;
}

/** The clinics and doctors the person has named for the pets they can reach (every record, not the last few). */
export interface KnownPlaces {
  clinics: string[];
  doctors: { name: string; clinic: string | null }[];
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
  protects?: string | null;
  complaint: string | null;
  diagnosis: string | null;
  recommendations: string | null;
  /** A visit names the weighing said at it; an edit sends it again, or the full replace clears it. */
  weight_event_id?: string | null;
  document_ids: string[];
  /** The version the edit was made from: a record changed since answers 409 instead of being overwritten. */
  base_version?: string | null;
}

export const medicalRecordsService = {
  async get(id: string): Promise<MedicalRecord> {
    const response = await api.get<{ record: MedicalRecord }>(`/medical-records/${id}`, { params: { tz: deviceTimeZone() } });
    return response.data.record;
  },

  /** Every record of a kind (the card shows the latest ten), newest first; without a kind, the pet's records of every kind. */
  async list(petId: string, kind?: MedicalKind): Promise<MedicalRecord[]> {
    const response = await api.get<{ records: MedicalRecord[] }>('/medical-records', { params: { pet_id: petId, kind, tz: deviceTimeZone() } });
    return response.data.records;
  },

  async places(): Promise<KnownPlaces> {
    const response = await api.get<KnownPlaces>('/medical-records/places');
    return response.data;
  },

  async create(petId: string, kind: MedicalKind, data: MedicalRecordInput, formKey?: string): Promise<string> {
    const body = { ...data, pet_id: petId, kind };
    const response = await api.post<{ id: string }>('/medical-records', body, { headers: idempotencyHeaders(formKey, body) });
    return response.data.id;
  },

  async update(id: string, data: MedicalRecordInput): Promise<void> {
    await api.put(`/medical-records/${id}`, data);
  },

  /** Takes a record away at once: «Отменить» after it was just added. */
  async delete(id: string): Promise<void> {
    await api.delete(`/medical-records/${id}`);
  },
};

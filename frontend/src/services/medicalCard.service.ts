import api from './api';
import type { MedicalKind, MedicalRecord } from './medicalRecords.service';
import { deviceTimeZone } from '../utils/timezone';
import { filenameFromResponse, saveBlob } from '../utils/download';

export interface MedicalCardWeightPoint {
  date: string;
  value: number;
}

export interface MedicalCardVaccination {
  id: string;
  title: string;
  expires_at: string | null;
  status: 'none' | 'valid' | 'soon' | 'expired';
  days_left: number | null;
  note: string | null;
}

export interface MedicalAllergy {
  substance: string;
  reaction?: string | null;
}

export interface MedicalCondition {
  name: string;
  since_year?: number | null;
  note?: string | null;
}

export interface MedicalDoctor {
  name: string;
  /** «Терапевт», «кардиолог», «стоматолог». */
  specialty?: string | null;
}

export interface MedicalClinic {
  name?: string | null;
  phone?: string | null;
  doctors: MedicalDoctor[];
}

/** What a vet asks first, kept on the pet; anyone with access may edit it. */
export interface MedicalProfile {
  chip_number?: string | null;
  blood_type?: string | null;
  allergies: MedicalAllergy[];
  /** «Аллергий нет»: a statement, not the same as nothing filled in. */
  allergies_none_known: boolean;
  /** Чем и как часто кормят. */
  diet?: string | null;
  /** Квартира или улица, другие животные. */
  living?: string | null;
  /** Беременности, роды, течка, если важно. */
  reproduction?: string | null;
  conditions: MedicalCondition[];
  /** The clinics the pet is taken to, the first is the main one; each with its doctors. */
  clinics: MedicalClinic[];
  /** The main clinic and its first doctor: the same as the first of `clinics`. */
  clinic: { name?: string | null; vet?: string | null; phone?: string | null };
  updated_at?: string | null;
}

export interface MedicalCardCourse {
  id: string;
  name: string;
  type: string | null;
  strength: string | null;
  dose_text: string | null;
  schedule_text: string;
  comment: string | null;
  purpose: string | null;
  prescribed_by: string | null;
  status: 'active' | 'planned' | 'ended';
  started_on: string | null;
  ended_on: string | null;
  given: number;
  skipped: number;
}

export const VISIT_CHECKS = ['appetite', 'thirst', 'stool', 'urine', 'vomiting', 'cough', 'activity'] as const;
export type VisitCheck = (typeof VISIT_CHECKS)[number];
export const VISIT_CHECK_LABELS: Record<VisitCheck, string> = {
  appetite: 'Аппетит',
  thirst: 'Жажда',
  stool: 'Стул',
  urine: 'Моча',
  vomiting: 'Рвота',
  cough: 'Кашель',
  activity: 'Активность',
};

/** What to tell the vet at the next appointment: the complaint and what has changed. */
export interface VisitPrep {
  complaint: string | null;
  /** «normal»: as usual, «changed»: not as usual; a check that is not there was not answered. */
  checks: Partial<Record<VisitCheck, 'normal' | 'changed'>>;
  updated_at?: string | null;
}

export interface MedicalCard {
  /** Nothing when it is not filled in. */
  visit_prep: VisitPrep | null;
  pet: {
    name: string;
    species: string | null;
    breed: string | null;
    birth_date: string | null;
    age_text: string | null;
    gender: string | null;
    neutered_text: string | null;
    health_notes: string | null;
  };
  profile: MedicalProfile;
  weight: { latest: MedicalCardWeightPoint; series: MedicalCardWeightPoint[] } | null;
  /** By kind, newest first, at most ten each. */
  records: Record<MedicalKind, MedicalRecord[]>;
  record_counts: Record<MedicalKind, number>;
  /** Courses going on or still to begin. */
  medications: MedicalCardCourse[];
  /** Finished courses, the latest first, at most ten. */
  past_courses: MedicalCardCourse[];
  past_courses_total: number;
  vaccinations: MedicalCardVaccination[];
  documents: { id: string; title: string; category: string; added: string }[];
  generated_at: string;
  can_edit: boolean;
}

async function savePdf(path: string, fallbackName: string): Promise<void> {
  const response = await api.get(path, { params: { tz: deviceTimeZone() }, responseType: 'blob' });
  saveBlob(response.data, filenameFromResponse(response.headers['content-disposition']) ?? fallbackName, 'application/pdf');
}

/** A pet's medical card, built on the server from the pet's own records. */
export interface MedicalAlerts {
  vaccination: boolean;
  parasite: boolean;
}

export const medicalCardService = {
  /** What is overdue, without the card: the dot on the «Медкарта» tab. */
  async alerts(petId: string): Promise<MedicalAlerts> {
    const response = await api.get<{ alerts: MedicalAlerts }>(`/pets/${petId}/medical-card/alerts`, {
      params: { tz: deviceTimeZone() },
    });
    return response.data.alerts;
  },

  async get(petId: string): Promise<MedicalCard> {
    const response = await api.get<{ card: MedicalCard }>(`/pets/${petId}/medical-card`, {
      params: { tz: deviceTimeZone() },
    });
    return response.data.card;
  },

  async saveVisitPrep(petId: string, prep: { complaint: string | null; checks: VisitPrep['checks'] }): Promise<VisitPrep | null> {
    const response = await api.put<{ visit_prep: VisitPrep | null }>(`/pets/${petId}/visit-prep`, prep);
    return response.data.visit_prep;
  },

  /** An empty one clears it: what was said at the visit is not carried to the next. */
  async clearVisitPrep(petId: string): Promise<void> {
    await api.put(`/pets/${petId}/visit-prep`, { complaint: null, checks: {} });
  },

  async saveProfile(petId: string, profile: Omit<MedicalProfile, 'updated_at'>): Promise<MedicalProfile> {
    const response = await api.put<{ profile: MedicalProfile }>(`/pets/${petId}/medical-profile`, profile);
    return response.data.profile;
  },

  /** Downloads the card as a PDF, to hand to a vet: page one is «now», the rest is the whole history. */
  async downloadPdf(petId: string, petName: string): Promise<void> {
    await savePdf(`/pets/${petId}/medical-card/pdf`, `${petName}.pdf`);
  },
};

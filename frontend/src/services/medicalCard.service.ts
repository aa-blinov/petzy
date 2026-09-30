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

/** What a vet asks first, kept on the pet; anyone with access may edit it. */
export interface MedicalProfile {
  chip_number?: string | null;
  blood_type?: string | null;
  allergies: MedicalAllergy[];
  /** «Аллергий нет»: a statement, not the same as nothing filled in. */
  allergies_none_known: boolean;
  conditions: MedicalCondition[];
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

export interface MedicalCard {
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
export const medicalCardService = {
  async get(petId: string): Promise<MedicalCard> {
    const response = await api.get<{ card: MedicalCard }>(`/pets/${petId}/medical-card`, {
      params: { tz: deviceTimeZone() },
    });
    return response.data.card;
  },

  async saveProfile(petId: string, profile: Omit<MedicalProfile, 'updated_at'>): Promise<MedicalProfile> {
    const response = await api.put<{ profile: MedicalProfile }>(`/pets/${petId}/medical-profile`, profile);
    return response.data.profile;
  },

  /** Downloads the same card as a PDF, to hand to a vet. */
  async downloadPdf(petId: string, petName: string): Promise<void> {
    await savePdf(`/pets/${petId}/medical-card/pdf`, `${petName}.pdf`);
  },

  /** The whole life history as a PDF: the card without its limits, oldest first. */
  async downloadAnamnesis(petId: string, petName: string): Promise<void> {
    await savePdf(`/pets/${petId}/anamnesis/pdf`, `анамнез_${petName}.pdf`);
  },
};

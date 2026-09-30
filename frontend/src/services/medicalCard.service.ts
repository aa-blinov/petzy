import api from './api';
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
  weight: { latest: MedicalCardWeightPoint; series: MedicalCardWeightPoint[] } | null;
  /** Courses going on or still to begin. */
  medications: MedicalCardCourse[];
  /** Finished courses, the latest first. */
  past_courses: MedicalCardCourse[];
  vaccinations: MedicalCardVaccination[];
  documents: { id: string; title: string; category: string; added: string }[];
  generated_at: string;
  can_edit: boolean;
}

/** A pet's medical card, built on the server from the pet's own records. */
export const medicalCardService = {
  async get(petId: string): Promise<MedicalCard> {
    const response = await api.get<{ card: MedicalCard }>(`/pets/${petId}/medical-card`, {
      params: { tz: deviceTimeZone() },
    });
    return response.data.card;
  },

  /** Downloads the same card as a PDF, to hand to a vet. */
  async downloadPdf(petId: string, petName: string): Promise<void> {
    const response = await api.get(`/pets/${petId}/medical-card/pdf`, {
      params: { tz: deviceTimeZone() },
      responseType: 'blob',
    });
    saveBlob(response.data, filenameFromResponse(response.headers['content-disposition']) ?? `${petName}.pdf`, 'application/pdf');
  },
};

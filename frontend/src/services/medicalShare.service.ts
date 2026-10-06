import api from './api';
import type { MedicalCard } from './medicalCard.service';
import { deviceTimeZone } from '../utils/timezone';
import { filenameFromResponse, saveBlob } from '../utils/download';

export interface MedicalShare {
  id: string;
  /** Who made it; empty when that account is gone. */
  username: string;
  created_at: string;
  expires_at: string;
}

export interface CreatedShare {
  share: MedicalShare;
  /** The secret: shown once, the server keeps only its hash. */
  token: string;
  path: string;
}

/** A link to the card for a vet: read-only, with an end, taken back at once. */
export const medicalShareService = {
  async create(petId: string, days: 1 | 7 | 30): Promise<CreatedShare> {
    const response = await api.post<CreatedShare>(`/pets/${petId}/medical-card/shares`, { days });
    return response.data;
  },
  async list(petId: string): Promise<MedicalShare[]> {
    const response = await api.get<{ shares: MedicalShare[] }>(`/pets/${petId}/medical-card/shares`);
    return response.data.shares;
  },
  async revoke(petId: string, shareId: string): Promise<void> {
    await api.delete(`/pets/${petId}/medical-card/shares/${shareId}`);
  },
  /** What the vet opens: the card and when the link ends. No sign-in. */
  async open(token: string): Promise<{ card: MedicalCard; expires_at: string; pet_id?: string }> {
    const response = await api.get<{ card: MedicalCard; expires_at: string; pet_id?: string }>(`/shared/medical-card/${encodeURIComponent(token)}`, { params: { tz: deviceTimeZone() } });
    return response.data;
  },
  async downloadPdf(token: string, petName: string): Promise<boolean> {
    const response = await api.get(`/shared/medical-card/${encodeURIComponent(token)}/pdf`, { params: { tz: deviceTimeZone() }, responseType: 'blob' });
    return saveBlob(response.data, filenameFromResponse(response.headers['content-disposition']) ?? `${petName}.pdf`, 'application/pdf');
  },
};

/** The address to give out: the page for the link on this site. */
export const shareUrl = (path: string) => `${window.location.origin}${path}`;

/** When a link ends, as the Russian reader writes it: 05.10.2026, 18:16. */
export const formatShareEnd = (iso: string) => new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });

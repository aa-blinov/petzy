import api from './api';
import type { FormSettings } from '../utils/formsConfig';
import type { TilesSettings } from '../utils/tilesConfig';

export interface PetInvite {
  pet_id: string;
  pet_name: string;
  species?: string | null;
  owner: string;
}

export interface Pet {
  _id: string;
  name: string;
  species?: string;
  breed?: string;
  birth_date?: string;
  gender?: string;
  is_neutered?: boolean;
  health_notes?: string;
  photo_url?: string;
  tiles_settings?: TilesSettings;
  /** What a new record of each built-in type starts with for this pet; everyone with access sees the same. */
  form_defaults?: FormSettings;
  owner: string;
  shared_with?: string[];
  /** Invited, not yet accepted. Present for the owner only. */
  share_invites?: string[];
  created_at?: string;
  current_user_is_owner?: boolean;
}

export interface PetCreate {
  name: string;
  species?: string;
  breed?: string;
  birth_date?: string;
  gender?: string;
  is_neutered?: boolean;
  health_notes?: string;
  photo_file?: File;
  photo_url?: string;
  tiles_settings?: TilesSettings;
}

export interface PetUpdate {
  name?: string;
  species?: string;
  breed?: string;
  birth_date?: string;
  gender?: string;
  is_neutered?: boolean;
  health_notes?: string;
  photo_file?: File;
  photo_url?: string;
  remove_photo?: boolean;
  tiles_settings?: TilesSettings;
}

export interface PetListResponse {
  pets: Pet[];
}

export interface PetResponse {
  pet: Pet;
}

export interface PetShareRequest {
  username: string;
}

export interface PetDeletionImpact {
  events: number;
  medications: number;
  documents: number;
  medical_records: number;
}

export const petsService = {
  async getPets(): Promise<Pet[]> {
    const response = await api.get<PetListResponse>('/pets');
    return response.data.pets;
  },

  /** Replaces the pet's form defaults; anyone who can add its records may. */
  async saveFormDefaults(petId: string, settings: FormSettings): Promise<FormSettings> {
    const response = await api.put<{ form_defaults: FormSettings }>(`/pets/${petId}/form-defaults`, { form_defaults: settings });
    return response.data.form_defaults;
  },

  /** What deleting the pet would take with it: the numbers its confirmation names. */
  async deletionImpact(petId: string): Promise<PetDeletionImpact> {
    const response = await api.get<PetDeletionImpact>(`/pets/${petId}/deletion-impact`);
    return response.data;
  },

  async getPet(petId: string): Promise<Pet> {
    const response = await api.get<PetResponse>(`/pets/${petId}`);
    return response.data.pet;
  },

  async createPet(data: PetCreate): Promise<Pet> {
    const formData = new FormData();
    formData.append('name', data.name);
    if (data.species) formData.append('species', data.species);
    if (data.breed) formData.append('breed', data.breed);
    if (data.birth_date) formData.append('birth_date', data.birth_date);
    if (data.gender) formData.append('gender', data.gender);
    if (data.is_neutered !== undefined) formData.append('is_neutered', String(data.is_neutered));
    if (data.health_notes) formData.append('health_notes', data.health_notes);
    if (data.photo_file) formData.append('photo_file', data.photo_file);
    if (data.photo_url) formData.append('photo_url', data.photo_url);
    if (data.tiles_settings) {
      formData.append('tiles_settings', JSON.stringify(data.tiles_settings));
    }

    const response = await api.post<{ message: string; pet: Pet }>('/pets', formData, { timeout: 120_000 });
    return response.data.pet;
  },

  async updatePet(petId: string, data: PetUpdate): Promise<Pet> {
    const formData = new FormData();
    if (data.name) formData.append('name', data.name);
    if (data.species !== undefined) formData.append('species', data.species);
    if (data.breed !== undefined) formData.append('breed', data.breed);
    if (data.birth_date !== undefined) formData.append('birth_date', data.birth_date);
    if (data.gender !== undefined) formData.append('gender', data.gender);
    if (data.is_neutered !== undefined) formData.append('is_neutered', String(data.is_neutered));
    if (data.health_notes !== undefined) formData.append('health_notes', data.health_notes);
    if (data.photo_file) formData.append('photo_file', data.photo_file);
    if (data.photo_url !== undefined) formData.append('photo_url', data.photo_url);
    if (data.remove_photo) formData.append('remove_photo', 'true');
    if (data.tiles_settings !== undefined) {
      formData.append('tiles_settings', JSON.stringify(data.tiles_settings));
    }

    const response = await api.put<{ message: string; pet: Pet }>(`/pets/${petId}`, formData, { timeout: 120_000 });
    return response.data.pet;
  },

  async deletePet(petId: string): Promise<void> {
    await api.delete(`/pets/${petId}`);
  },

  /** Sends an invitation: access starts once they accept it. */
  async sharePet(petId: string, username: string): Promise<void> {
    await api.post(`/pets/${petId}/share`, { username });
  },

  async getInvites(): Promise<PetInvite[]> {
    const response = await api.get<{ invites: PetInvite[] }>('/pets/invites');
    return response.data.invites;
  },

  async acceptInvite(petId: string): Promise<void> {
    await api.post(`/pets/${petId}/invite/accept`);
  },

  async declineInvite(petId: string): Promise<void> {
    await api.post(`/pets/${petId}/invite/decline`);
  },

  /** Stop seeing a pet someone shared. */
  async leavePet(petId: string): Promise<void> {
    await api.post(`/pets/${petId}/leave`);
  },

  async unsharePet(petId: string, username: string): Promise<void> {
    await api.delete(`/pets/${petId}/share/${username}`);
  },

  getPetPhotoUrl(petId: string): string {
    return `/api/pets/${petId}/photo`;
  }
};


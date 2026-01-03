import api from './api';

export interface Pet {
  _id: string;
  name: string;
  species?: string;
  breed?: string;
  birth_date?: string;
  photo_url?: string;
  photo_file_id?: string;
  owner: string;
  shared_with?: string[];
  created_at?: string;
  current_user_is_owner?: boolean;
}

export interface PetCreate {
  name: string;
  species?: string;
  breed?: string;
  birth_date?: string;
  photo_file?: File;
  photo_url?: string;
}

export interface PetUpdate {
  name?: string;
  species?: string;
  breed?: string;
  birth_date?: string;
  photo_file?: File;
  photo_url?: string;
  remove_photo?: boolean;
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

export const petsService = {
  async getPets(): Promise<Pet[]> {
    const response = await api.get<PetListResponse>('/pets');
    return response.data.pets;
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
    if (data.photo_file) formData.append('photo_file', data.photo_file);
    if (data.photo_url) formData.append('photo_url', data.photo_url);

    const response = await api.post<{ message: string; pet: Pet }>('/pets', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data.pet;
  },

  async updatePet(petId: string, data: PetUpdate): Promise<Pet> {
    const formData = new FormData();
    if (data.name) formData.append('name', data.name);
    if (data.species) formData.append('species', data.species);
    if (data.breed) formData.append('breed', data.breed);
    if (data.birth_date) formData.append('birth_date', data.birth_date);
    if (data.photo_file) formData.append('photo_file', data.photo_file);
    if (data.photo_url) formData.append('photo_url', data.photo_url);
    if (data.remove_photo) formData.append('remove_photo', 'true');

    const response = await api.put<{ message: string; pet: Pet }>(`/pets/${petId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data.pet;
  },

  async deletePet(petId: string): Promise<void> {
    await api.delete(`/pets/${petId}`);
  },

  async sharePet(petId: string, username: string): Promise<void> {
    await api.post(`/pets/${petId}/share`, { username });
  },

  async unsharePet(petId: string, username: string): Promise<void> {
    await api.delete(`/pets/${petId}/share/${username}`);
  },

  getPetPhotoUrl(petId: string): string {
    return `/api/pets/${petId}/photo`;
  }
};


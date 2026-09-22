import api from './api';

export type DocumentCategory = 'vaccination' | 'lab_result' | 'conclusion' | 'insurance' | 'other';

export const DOCUMENT_CATEGORY_LABELS: Record<DocumentCategory, string> = {
  vaccination: 'Прививки',
  lab_result: 'Анализы',
  conclusion: 'Заключения',
  insurance: 'Страховка',
  other: 'Другое',
};

export interface PetDocument {
  _id: string;
  pet_id: string;
  username: string;
  category: DocumentCategory;
  title: string;
  note?: string;
  original_filename: string;
  content_type: string;
  file_size: number;
  created_at: string;
}

export interface DocumentCreateInput {
  pet_id: string;
  category: DocumentCategory;
  title: string;
  note?: string;
  file: File;
}

export interface DocumentUpdateInput {
  category?: DocumentCategory;
  title?: string;
  note?: string;
}

export interface DocumentListResponse {
  documents: PetDocument[];
  page: number;
  page_size: number;
  total: number;
}

export const documentsService = {
  async getList(petId: string, category?: DocumentCategory): Promise<DocumentListResponse> {
    const response = await api.get<DocumentListResponse>('/documents', {
      params: { pet_id: petId, category, page: 1, page_size: 100 },
    });
    return response.data;
  },

  async getById(id: string): Promise<PetDocument> {
    const response = await api.get<{ document: PetDocument }>(`/documents/${id}`);
    return response.data.document;
  },

  async create(data: DocumentCreateInput): Promise<string> {
    const formData = new FormData();
    formData.append('pet_id', data.pet_id);
    formData.append('category', data.category);
    formData.append('title', data.title);
    if (data.note) formData.append('note', data.note);
    formData.append('file', data.file);

    const response = await api.post<{ message: string; id: string }>('/documents', formData);
    return response.data.id;
  },

  async update(id: string, data: DocumentUpdateInput): Promise<void> {
    await api.put(`/documents/${id}`, data);
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/documents/${id}`);
  },

  getFileUrl(id: string): string {
    return `/api/documents/${id}/file`;
  },
};

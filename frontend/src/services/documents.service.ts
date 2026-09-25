import api from './api';

export type DocumentCategory = 'vaccination' | 'lab_result' | 'conclusion' | 'imaging' | 'insurance' | 'other';

export const DOCUMENT_CATEGORY_LABELS: Record<DocumentCategory, string> = {
  vaccination: 'Прививки',
  lab_result: 'Анализы',
  conclusion: 'Заключения',
  imaging: 'Снимки',
  insurance: 'Страховка',
  other: 'Другое',
};

/** Scans (MRI/CT/X-ray exports) come as archives or DICOM files; the same
 *  list the backend accepts (SCAN_FORMATS in web/storage.py). */
export const SCAN_EXTENSIONS = ['.zip', '.7z', '.rar', '.tar', '.tar.gz', '.tgz', '.gz', '.dcm', '.iso'];

export function isScanFilename(name: string): boolean {
  const lower = name.toLowerCase();
  return SCAN_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export interface StorageStatus {
  scans_enabled: boolean;
  max_scan_bytes: number;
}

interface ScanUploadSlot {
  upload_id: string;
  upload_url: string;
  content_type: string;
  max_bytes: number;
}

export interface ScanCreateInput {
  pet_id: string;
  title: string;
  note?: string;
  expires_at?: string;
  file: File;
  onProgress?: (fraction: number) => void;
  signal?: AbortSignal;
}

/** PUT straight to the bucket's signed URL. XHR rather than fetch: fetch
 *  still can't report upload progress, and a 500 MB upload needs it. */
function putToSignedUrl(url: string, file: File, contentType: string, onProgress?: (f: number) => void, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', url);
    xhr.setRequestHeader('Content-Type', contentType);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded / e.total);
    };
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new ScanUploadError('upload')));
    xhr.onerror = () => reject(new ScanUploadError('network'));
    xhr.onabort = () => reject(new DOMException('Upload cancelled', 'AbortError'));
    signal?.addEventListener('abort', () => xhr.abort(), { once: true });
    xhr.send(file);
  });
}

export class ScanUploadError extends Error {
  readonly reason: 'upload' | 'network';

  constructor(reason: 'upload' | 'network') {
    super(reason === 'network' ? 'Нет связи с хранилищем. Проверьте интернет и попробуйте ещё раз' : 'Хранилище не приняло файл. Попробуйте ещё раз');
    this.reason = reason;
  }
}

export interface PetDocument {
  _id: string;
  pet_id: string;
  username: string;
  category: DocumentCategory;
  title: string;
  note?: string;
  /** "YYYY-MM-DD", when this document (a vaccination cert, an insurance
   *  policy, etc.) stops being valid. Optional — not every category has
   *  one (lab results, conclusions usually don't). */
  expires_at?: string;
  original_filename: string;
  content_type: string;
  file_size: number;
  /** A scan archive: downloaded, not previewed. */
  scan?: boolean;
  created_at: string;
}

export interface DocumentCreateInput {
  pet_id: string;
  category: DocumentCategory;
  title: string;
  note?: string;
  expires_at?: string;
  file: File;
}

export interface DocumentUpdateInput {
  category?: DocumentCategory;
  title?: string;
  note?: string;
  expires_at?: string;
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
    if (data.expires_at) formData.append('expires_at', data.expires_at);
    formData.append('file', data.file);

    const response = await api.post<{ message: string; id: string }>('/documents', formData);
    return response.data.id;
  },

  async getStorageStatus(): Promise<StorageStatus> {
    const response = await api.get<StorageStatus>('/documents/storage');
    return response.data;
  },

  /** Reserve a slot, upload the file straight to storage, then confirm:
   *  the backend checks the stored size and format before the document
   *  appears. */
  async createScan(data: ScanCreateInput): Promise<string> {
    const { data: slot } = await api.post<ScanUploadSlot>('/documents/scans', {
      pet_id: data.pet_id,
      filename: data.file.name,
      size: data.file.size,
    });
    await putToSignedUrl(slot.upload_url, data.file, slot.content_type, data.onProgress, data.signal);
    const response = await api.post<{ message: string; id: string }>(`/documents/scans/${slot.upload_id}/complete`, {
      title: data.title,
      note: data.note || undefined,
      expires_at: data.expires_at || undefined,
    });
    return response.data.id;
  },

  async update(id: string, data: DocumentUpdateInput): Promise<void> {
    await api.put(`/documents/${id}`, data);
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/documents/${id}`);
  },

  /** Where to download the file from: for a scan, a short-lived signed
   *  link to storage. Asked for first, so an error (session gone, access
   *  revoked) reaches the page instead of replacing it. */
  async getDownloadUrl(id: string): Promise<string> {
    const response = await api.get<{ url: string }>(`/documents/${id}/download`);
    return response.data.url;
  },

  getFileUrl(id: string): string {
    return `/api/documents/${id}/file`;
  },
};

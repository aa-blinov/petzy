import api from './api';
import { utcStampToLocal } from '../utils/dateUtils';

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

/** Whether a request ended because the user pressed «Остановить», not because it failed. */
export function isUploadCancelled(err: unknown): boolean {
  if (err instanceof DOMException && err.name === 'AbortError') return true;
  return typeof err === 'object' && err !== null && (err as { code?: string }).code === 'ERR_CANCELED';
}

/** An id for one upload attempt, 32 hex characters: the shape the server
 *  accepts on `upload_id`. It lets «Остановить» name the upload it cut, so
 *  a file the server had already stored can be taken back. */
function uploadId(): string {
  const raw = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : '';
  const fallback = `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
  return (raw || fallback).replace(/-/g, '').toLowerCase().padEnd(32, '0').slice(0, 32);
}

/** How much of the body has gone (0..1). axios reports it through the XHR
 *  upload progress event, the same one the signed-PUT upload uses. */
function uploadFraction(e: { loaded?: number; total?: number; bytes?: number }): number {
  const total = e.total ?? e.bytes;
  if (!total) return 0;
  return Math.min(1, (e.loaded ?? 0) / total);
}

/** A record of the medical card that holds a document: where the file came from, and what it can be found by. */
export interface DocumentRecordRef {
  id: string;
  kind?: string | null;
  title: string;
  date?: string | null;
  diagnosis?: string | null;
  clinic?: string | null;
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
  /** The zone the file was added in, as an IANA name. Absent for documents
   *  added before the field: their zone is unknown, so their time is read
   *  on the clock of whoever is looking. */
  tz?: string | null;
  created_at: string;
  /** The kinds of medical-card record that point at this document (vaccination, visit...). */
  medical_record_kinds?: string[];
  /** A record with a repeat date points at this document and reminds about it. */
  record_reminds?: boolean;
  /** The records that hold this document, newest first. */
  medical_records?: DocumentRecordRef[];
}

/** Attached to a vaccination or treatment record, so the document has become part of the card. */
export function isInMedicalCard(doc: Pick<PetDocument, 'medical_record_kinds'>): boolean {
  return (doc.medical_record_kinds ?? []).some((k) => k === 'vaccination' || k === 'parasite');
}

/** What deleting a document asks, in one wording for both places that ask it:
 *  the list's dialog and the form's. The list used a shorter text that said
 *  nothing about the file itself being erased for good. */
export function documentDeleteText(doc: Pick<PetDocument, 'title' | 'medical_record_kinds'>): string {
  const attached = (doc.medical_record_kinds ?? []).length > 0;
  return `Удалить документ «${doc.title}»?${attached ? ' Он прикреплён к записям медкарты: сами записи останутся, а документ из них пропадёт' : ''} Файл будет стёрт насовсем`;
}

/** The record has a repeat date and reminds about it itself, so the document's own expiry is not shown as a second,
 *  possibly stale, verdict. A record with no repeat date reminds about nothing: the document's date stays. */
export function isCoveredByMedicalCard(doc: Pick<PetDocument, 'record_reminds'>): boolean {
  return doc.record_reminds === true;
}

/** Formatters per zone: one object each, built once — the list asks for the
 *  same zone once per document, and building a formatter is not free. */
const zoneFormatters = new Map<string, Intl.DateTimeFormat>();

function zoneFormatter(zone: string): Intl.DateTimeFormat | null {
  const cached = zoneFormatters.get(zone);
  if (cached) return cached;
  try {
    const formatter = new Intl.DateTimeFormat('en-CA', {
      timeZone: zone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    });
    zoneFormatters.set(zone, formatter);
    return formatter;
  } catch {
    return null;
  }
}

/** The wall clock of a document's own zone, as «YYYY-MM-DD HH:MM»: what
 *  «Добавлен <дата>» is built from. The server stamps the moment in UTC, so
 *  a document with a zone is read on that zone's clock and every reader sees
 *  the same time. A document from before the field has no zone — there the
 *  time stays on the clock of whoever is looking, which is all that is known
 *  about it. */
export function documentLocalStamp(doc: Pick<PetDocument, 'created_at' | 'tz'>): string {
  if (doc.tz) {
    const iso = doc.created_at.replace(' ', 'T');
    const moment = new Date(iso.length === 16 ? `${iso}:00Z` : `${iso}Z`);
    const formatter = Number.isNaN(moment.getTime()) ? null : zoneFormatter(doc.tz);
    if (formatter) {
      const parts = formatter.formatToParts(moment);
      const part = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
      const stamp = `${part('year')}-${part('month')}-${part('day')} ${part('hour')}:${part('minute')}`;
      if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(stamp)) return stamp;
    }
  }
  return utcStampToLocal(doc.created_at);
}

export interface DocumentCreateInput {
  pet_id: string;
  category: DocumentCategory;
  title: string;
  note?: string;
  expires_at?: string;
  /** The zone the file is added in, so «Добавлен <дата>» reads the same for everyone. */
  tz?: string;
  file: File;
  onProgress?: (fraction: number) => void;
  signal?: AbortSignal;
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

  /** Upload a photo or a PDF. The same progress and «Остановить» as a scan
   *  archive: a file of up to 10 MB on a phone connection is worth a counter,
   *  and a stopped upload asks the server to drop what it may have stored. */
  async create(data: DocumentCreateInput): Promise<string> {
    const id = uploadId();
    const formData = new FormData();
    formData.append('pet_id', data.pet_id);
    formData.append('category', data.category);
    formData.append('title', data.title);
    if (data.note) formData.append('note', data.note);
    if (data.expires_at) formData.append('expires_at', data.expires_at);
    if (data.tz) formData.append('tz', data.tz);
    formData.append('upload_id', id);
    formData.append('file', data.file);

    // A file of up to 10 MB on a phone connection: given longer than an ordinary request.
    try {
      const response = await api.post<{ message: string; id: string }>('/documents', formData, {
        timeout: 120_000,
        signal: data.signal,
        onUploadProgress: (e) => data.onProgress?.(uploadFraction(e)),
      });
      return response.data.id;
    } catch (err) {
      // The request was cut, but the server may have answered and stored the
      // file before the answer reached us: name the upload so it can be taken back.
      if (isUploadCancelled(err)) await documentsService.cancelUpload(id);
      throw err;
    }
  },

  /** Put another file behind a document: the old one is removed by the server
   *  only once the new one is there and the document says so. */
  async replaceFile(id: string, file: File, onProgress?: (f: number) => void, signal?: AbortSignal): Promise<void> {
    const formData = new FormData();
    formData.append('file', file);
    await api.put(`/documents/${id}/file`, formData, {
      timeout: 120_000,
      signal,
      onUploadProgress: (e) => onProgress?.(uploadFraction(e)),
    });
  },

  /** Ask the server to drop the document a stopped upload made, with its file.
   *  Nothing to remove (the request never arrived) is a success too. */
  async cancelUpload(uploadId: string): Promise<void> {
    try {
      await api.post(`/documents/uploads/${uploadId}/cancel`);
    } catch {
      // The upload was stopped on purpose; a failed clean-up must not add a second message.
    }
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

/** The documents list query, shared by the page and the tab prefetch
 *  (App.tsx) so both fill the same cache entry. */
export function documentsListQuery(petId: string) {
  return {
    queryKey: ['documents', petId] as const,
    queryFn: () => documentsService.getList(petId).then((res) => res.documents),
  };
}

/**
 * Documents and the records that hold them: the pure parts of «Прикрепить к записи» and «Открепить».
 *
 * A record's PUT is a full replace, so attaching or detaching a document sends every field of the record again, with only the list
 * of its documents changed. The pieces here build that body and the rows of the picker; nothing here talks to the server.
 */

import type { MedicalKind, MedicalRecord, MedicalRecordInput } from '../services/medicalRecords.service';
import { MEDICAL_KIND_LABELS, medicalRecordsService } from '../services/medicalRecords.service';
import { formatDate } from './medicalCardFormat';

/** The server's limit: a record holds at most ten documents. */
export const MAX_RECORD_DOCUMENTS = 10;

/** «Визит к врачу, 20.10.2026: Осмотр»: what a record is called in a list of records. The day and the title may be missing. */
export function recordLabel(record: { kind?: string | null; title?: string | null; date?: string | null }): string {
  const kind = record.kind && record.kind in MEDICAL_KIND_LABELS ? MEDICAL_KIND_LABELS[record.kind as MedicalKind].one : 'Запись';
  const head = record.date ? `${kind}, ${formatDate(record.date)}` : kind;
  return record.title ? `${head}: ${record.title}` : head;
}

export interface RecordRow {
  id: string;
  label: string;
  /** The document is already one of this record's. */
  attached: boolean;
  /** The record holds the most documents it can and this one is not among them. */
  full: boolean;
}

/** The pet's records as the picker lists them: newest first (the same day keeps the order it came in), the ones that already hold
    the document marked, the ones with no room left marked as full. */
export function buildRecordRows(records: MedicalRecord[], documentId: string): RecordRow[] {
  return records
    .map((record, index) => ({ record, index }))
    .sort((a, b) => b.record.date.localeCompare(a.record.date) || a.index - b.index)
    .map(({ record }) => {
      const attached = record.documents.some((d) => d.id === documentId);
      return {
        id: record._id,
        label: recordLabel(record),
        attached,
        full: !attached && record.documents.length >= MAX_RECORD_DOCUMENTS,
      };
    });
}

/** The whole record as the PUT wants it, for a change of one thing. `base_version` is the version it was read at, so that a record
    somebody changed meanwhile answers 409 instead of being overwritten. */
export function recordToInput(record: MedicalRecord): MedicalRecordInput {
  return {
    date: record.date,
    title: record.title,
    next_due: record.next_due,
    clinic: record.clinic,
    vet: record.vet,
    note: record.note,
    batch: record.batch,
    target: record.target,
    protects: record.protects,
    complaint: record.complaint,
    diagnosis: record.diagnosis,
    recommendations: record.recommendations,
    weight_event_id: record.weight_event_id ?? null,
    document_ids: record.documents.map((d) => d.id),
    base_version: record.updated_at ?? null,
  };
}

/** The record with the document added, every other field as it was. Already there: the same list, once. */
export function withDocumentAdded(record: MedicalRecord, documentId: string): MedicalRecordInput {
  const input = recordToInput(record);
  if (!input.document_ids.includes(documentId)) input.document_ids = [...input.document_ids, documentId];
  return input;
}

/** The record with the document taken out of its list, every other field as it was. The file itself is not touched. */
export function withDocumentRemoved(record: MedicalRecord, documentId: string): MedicalRecordInput {
  const input = recordToInput(record);
  input.document_ids = input.document_ids.filter((id) => id !== documentId);
  return input;
}

/** Puts a document among a record's: the record is read again and sent whole, only its documents changed. */
export async function attachDocumentToRecord(recordId: string, documentId: string): Promise<void> {
  await medicalRecordsService.update(recordId, withDocumentAdded(await medicalRecordsService.get(recordId), documentId));
}

/** Lets go of a document: the record is read again and sent whole without it. The file stays among the documents. */
export async function detachDocumentFromRecord(recordId: string, documentId: string): Promise<void> {
  await medicalRecordsService.update(recordId, withDocumentRemoved(await medicalRecordsService.get(recordId), documentId));
}

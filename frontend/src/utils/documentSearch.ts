import { DOCUMENT_CATEGORY_LABELS, type PetDocument } from '../services/documents.service';

const normalize = (text: string) => text.toLowerCase().replace(/ё/g, 'е');

/** «2026-09-23» as it is read and typed: 23.09.2026. */
const dotted = (iso?: string | null) => (iso && /^\d{4}-\d{2}-\d{2}/.test(iso) ? `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}` : '');

/** Everything a person may remember a file by, in one line: its title, its kind, the note, the file's name, and what the
    records that hold it say (the reason of the visit, the diagnosis, the clinic, the day). */
export function documentSearchText(doc: PetDocument): string {
  const records = doc.medical_records ?? [];
  return normalize(
    [
      doc.title,
      DOCUMENT_CATEGORY_LABELS[doc.category],
      doc.note,
      doc.original_filename,
      dotted(doc.expires_at),
      ...records.flatMap((r) => [r.title, r.diagnosis, r.clinic, dotted(r.date)]),
    ]
      .filter(Boolean)
      .join(' '),
  );
}

/** Every word of the query must be somewhere in the file's line: «рентген ортовет» finds the picture taken there. */
export function matchesDocumentQuery(doc: PetDocument, query: string): boolean {
  const words = normalize(query).split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  const text = documentSearchText(doc);
  return words.every((w) => text.includes(w));
}

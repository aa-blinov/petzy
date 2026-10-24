import { describe, expect, it } from 'vitest'
import {
  MAX_RECORD_DOCUMENTS,
  buildRecordRows,
  recordLabel,
  withDocumentAdded,
  withDocumentRemoved,
} from '../../src/utils/documentRecords'
import type { MedicalRecord } from '../../src/services/medicalRecords.service'

function record(over: Partial<MedicalRecord> = {}): MedicalRecord {
  return {
    _id: 'r1',
    pet_id: 'p1',
    kind: 'visit',
    date: '2026-10-20',
    title: 'Осмотр',
    next_due: null,
    status: 'none',
    days_left: null,
    superseded: false,
    clinic: 'Ортовет',
    vet: 'Иванова',
    note: 'заметка',
    batch: null,
    target: null,
    protects: null,
    protects_label: null,
    complaint: 'вялость',
    diagnosis: 'ничего',
    recommendations: 'покой',
    weight_event_id: 'w1',
    documents: [{ id: 'd1', title: 'Анализ' }],
    updated_at: '2026-10-20T10:00:00.000000',
    ...over,
  }
}

describe('подпись записи в списке', () => {
  it('называет вид, день и повод', () => {
    expect(recordLabel(record())).toBe('Визит к врачу, 20.10.2026: Осмотр')
  })

  it('обходится без дня и без повода', () => {
    expect(recordLabel({ kind: 'vaccination' })).toBe('Прививка')
    expect(recordLabel({ kind: 'nope', title: 'Что-то' })).toBe('Запись: Что-то')
  })
})

describe('строки выбора записи', () => {
  it('идут от новых к старым', () => {
    const rows = buildRecordRows(
      [record({ _id: 'old', date: '2026-01-05' }), record({ _id: 'new', date: '2026-10-20' }), record({ _id: 'mid', date: '2026-05-01' })],
      'x',
    )
    expect(rows.map((r) => r.id)).toEqual(['new', 'mid', 'old'])
  })

  it('отмечают записи, к которым файл уже прикреплён', () => {
    const rows = buildRecordRows([record({ _id: 'a' }), record({ _id: 'b', documents: [] })], 'd1')
    expect(rows.find((r) => r.id === 'a')?.attached).toBe(true)
    expect(rows.find((r) => r.id === 'b')?.attached).toBe(false)
  })

  it('отмечают запись, в которой нет места, но не ту, где файл уже есть', () => {
    const ten = Array.from({ length: MAX_RECORD_DOCUMENTS }, (_, i) => ({ id: `f${i}`, title: `Файл ${i}` }))
    const rows = buildRecordRows([record({ _id: 'full', documents: ten }), record({ _id: 'has', documents: ten })], 'f3')
    // в обеих записях файл f3 уже есть: места нет, но и прикреплять нечего
    expect(rows.every((r) => r.attached && !r.full)).toBe(true)
    const other = buildRecordRows([record({ _id: 'full', documents: ten })], 'new-file')
    expect(other[0]).toMatchObject({ attached: false, full: true })
  })
})

describe('замена записи целиком', () => {
  it('добавляет файл и сохраняет все остальные поля и связь с весом', () => {
    const input = withDocumentAdded(record(), 'd2')
    expect(input.document_ids).toEqual(['d1', 'd2'])
    expect(input).toMatchObject({
      date: '2026-10-20',
      title: 'Осмотр',
      clinic: 'Ортовет',
      vet: 'Иванова',
      note: 'заметка',
      complaint: 'вялость',
      diagnosis: 'ничего',
      recommendations: 'покой',
      weight_event_id: 'w1',
      base_version: '2026-10-20T10:00:00.000000',
    })
  })

  it('не вносит один и тот же файл дважды', () => {
    expect(withDocumentAdded(record(), 'd1').document_ids).toEqual(['d1'])
  })

  it('убирает файл и сохраняет остальные поля и остальные файлы', () => {
    const two = record({ documents: [{ id: 'd1', title: 'А' }, { id: 'd2', title: 'Б' }], kind: 'vaccination', protects: 'rabies', batch: 'L1' })
    const input = withDocumentRemoved(two, 'd1')
    expect(input.document_ids).toEqual(['d2'])
    expect(input).toMatchObject({ protects: 'rabies', batch: 'L1', title: 'Осмотр' })
  })

  it('запись без связи с весом остаётся без неё', () => {
    expect(withDocumentAdded(record({ weight_event_id: undefined }), 'd2').weight_event_id).toBeNull()
  })
})
